from dataclasses import dataclass
from datetime import timedelta

import json_repair
from prompts import _SUMMARY_PROMPT
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import CallLLMInput, ExtractPDFInput, call_llm, extract_pdf

@dataclass
class PDFSummaryInput:
    s3_path: str

@dataclass(frozen=True)
class PDFSummaryOutput:
    s3_path: str
    summary: str
    key_risks: list[str]

DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=3
)

@workflow.defn
class PDFSummaryWorkflow:
    @workflow.run
    async def run(self, params: PDFSummaryInput) -> PDFSummaryOutput:
        workflow.logger.info("PDFSummaryWorkflow running")

        extracted_md = await workflow.execute_activity(
            extract_pdf,
            ExtractPDFInput(s3_path=params.s3_path),
            start_to_close_timeout=timedelta(minutes=15),
            heartbeat_timeout=timedelta(minutes=1),
            retry_policy = DEFAULT_RETRY_POLICY 
        )

        llm_output = await workflow.execute_activity(
            call_llm,
            CallLLMInput(prompt=_SUMMARY_PROMPT.format(text=extracted_md.markdown_text)),
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(minutes=1),
            retry_policy = DEFAULT_RETRY_POLICY 
        )

        parsed_data = json_repair.loads(llm_output.content)

        return PDFSummaryOutput(
            s3_path=params.s3_path,
            summary=parsed_data.get("summary", "No summary provided."),
            key_risks=parsed_data.get("key_risks", [])
        )
