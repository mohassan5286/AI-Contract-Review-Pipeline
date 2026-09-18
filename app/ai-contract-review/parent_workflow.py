import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta

import json_repair
from prompts import _REVISION_PROMPT, _SYNTHESIS_PROMPT
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from activities import CallLLMInput, call_llm
    from child_workflow import PDFSummaryInput, PDFSummaryWorkflow

@dataclass
class ContractReviewInput:
    s3_paths: list[str]
    max_revisions: int = 2

@dataclass
class ContractReviewOutput:
    report: str
    sources: list[str]
    approved_by: str

DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=4,
)

@workflow.defn
class ContractReviewWorkflow:
    def __init__(self):
        self._status = "pending"
        self._summaries = []
        self._report = ""

        self._review_decision : str | None = None
        self._review_feedback = ""
        self._approved_by = ""

    @workflow.query
    def get_status(self) -> dict:
        preview = self._report.get("overall_risk_level", "Generating...") if isinstance(self._report, dict) else str(self._report)
        return {
            "status":         self._status,
            "pdfs_processed": len(self._summaries),
            "report_preview": preview[:500],
            "approved_by":    self._approved_by,
        }
    
    @workflow.query
    def get_report(self) -> dict:
        return {
            "status":      self._status,
            "report":      self._report,
            "approved_by": self._approved_by,
            "sources":     [s["s3_path"] for s in self._summaries],
        }

    @workflow.signal
    async def assign_reviewer(self, name:str) -> str:
        self._approved_by = name
        return f"Assign Reviewer {name}"

    @workflow.update
    async def submit_decision(self, review_decision:str, review_feedback:str) -> str:
        self._review_decision = review_decision
        self._review_feedback = review_feedback
        return f"Decision '{review_decision}' recorded."

    @submit_decision.validator
    def validate_review_decision(self, review_decision: str, review_feedback: str) -> None:
        if review_decision not in ["approve", "revise"]:
            raise ValueError(f"Invalid review decision: {review_decision}")

        if review_decision == "revise" and not review_feedback.strip():
            raise ValueError("Review feedback is required for revise decision")        

    @workflow.run
    async def run(self, params: ContractReviewInput) -> ContractReviewOutput:    
        self._status = "extracting"
        workflow.logger.info(f"Fanning out to {len(params.s3_paths)} child workflows")

        workflow_id = workflow.info().workflow_id
        workflow_queue = workflow.info().task_queue

        results = await asyncio.gather(
            *[
                workflow.execute_child_workflow(
                    PDFSummaryWorkflow.run,
                    PDFSummaryInput(s3_path=s3_path),
                    retry_policy=DEFAULT_RETRY_POLICY,
                    id=f"{workflow_id}-pdf-{i}",
                    task_queue=workflow_queue,
                    parent_close_policy=ParentClosePolicy.ABANDON,
                )
                for i, s3_path in enumerate(params.s3_paths)
            ],
            return_exceptions=True
        )
        
        self._status = "synthesizing"

        for i, res in enumerate(results):
            if isinstance(res, Exception):
                workflow.logger.warning(f"PDF {i} failed: {res}")
            else:
                self._summaries.append({
                    "s3_path":   res.s3_path,
                    "summary":   res.summary,
                    "key_risks": res.key_risks,
                })

        n = len(self._summaries)
        combined_summary = "\n\n".join([
            f"**Contract {i+1}** (`{summary['s3_path']}`):\n"
            f"Summary: {summary['summary']}\n"
            f"Risks: {', '.join(summary['key_risks'])}"
            for i, summary in enumerate(self._summaries)
        ])

        llm_prompt = _SYNTHESIS_PROMPT.format(n=n, summaries=combined_summary)
        
        llm_output = await workflow.execute_activity(
            call_llm,
            CallLLMInput(prompt=llm_prompt),
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(minutes=1),
            retry_policy=DEFAULT_RETRY_POLICY 
        )
        
        self._report = json_repair.loads(llm_output.content)
    
        for i in range(params.max_revisions):
            self._status = "reviewing"
            
            self._review_decision = None

            try:
                await workflow.wait_condition(
                    lambda: self._review_decision is not None,
                    timeout=timedelta(days=3),
                )

            except asyncio.TimeoutError:
                workflow.logger.warning("Timed out waiting for review decision")
            
            if self._review_decision == "approve":
                workflow.logger.info(f"Approval by {self._approved_by}")
                break

            llm_prompt = _REVISION_PROMPT.format(
                report=json.dumps(self._report, ensure_ascii=False, indent=2),
                feedback=self._review_feedback,
            )

            llm_output = await workflow.execute_activity(
                call_llm,
                CallLLMInput(prompt=llm_prompt),
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(minutes=1),
                retry_policy=DEFAULT_RETRY_POLICY 
            )
            self._report = json_repair.loads(llm_output.content)

        self._status = "completed"
        return ContractReviewOutput(
            report=self._report,
            sources=[s["s3_path"] for s in self._summaries],
            approved_by=self._approved_by
        )
    