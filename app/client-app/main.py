import os
import uuid
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from temporalio.client import Client

load_dotenv()

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE")
TEMPORAL_PDF_PROCESS_TASK_QUEUE = os.getenv("TEMPORAL_PDF_PROCESS_TASK_QUEUE")
TEMPORAL_CONTRACT_REVIEW_TASK_QUEUE = os.getenv("TEMPORAL_CONTRACT_REVIEW_TASK_QUEUE")

# --- Temporal Models ---
@dataclass
class PDFProcessingWorkflowInput:
    s3_input_path: str

@dataclass
class PDFProcessingWorkflowOutput:
    s3_output_path: str

# --- API Models ---
class ProcessPDFExecuteRequest(BaseModel):
    s3_path: str

class ProcessPDFExecuteResponse(BaseModel):
    workflow_id: str
    result: PDFProcessingWorkflowOutput

class ProcessPDFStartRequest(BaseModel):
    s3_path: str

class ProcessPDFStartResponse(BaseModel):
    workflow_id: str

class ProcessPDFStatusResponse(BaseModel):
    workflow_id: str
    status: str

class StartReviewRequest(BaseModel):
    s3_paths: list[str]
    max_revisions: int = 2

class StartReviewResponse(BaseModel):
    workflow_id: str

class AssignRequest(BaseModel):
    workflow_id: str
    name: str

class ReviseRequest(BaseModel):
    workflow_id: str
    feedback: str

class ApproveRequest(BaseModel):
    workflow_id: str

# --- Temporal Client ---
async def get_client():
    return await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
    )

app = FastAPI(
    title="PDF Extraction Client",
    description="Submits PDF processing jobs to Temporal and returns the result.",
    version="1.0.0",
)

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- Routes ---

@app.post("/process-pdf/execute", response_model=ProcessPDFExecuteResponse)
async def process_pdf_execute(request: ProcessPDFExecuteRequest):
    client = await get_client()
    workflow_id = f"pdf-pipeline-{uuid.uuid4()}"
    
    result = await client.execute_workflow(
        "PDFProcessingWorkflow",
        arg=PDFProcessingWorkflowInput(s3_input_path=request.s3_path),
        id=workflow_id,
        task_queue=TEMPORAL_PDF_PROCESS_TASK_QUEUE,
    )

    return ProcessPDFExecuteResponse(
        workflow_id=workflow_id,
        result=result
    )

@app.post("/process-pdf/start", response_model=ProcessPDFStartResponse)
async def process_pdf_start(request: ProcessPDFStartRequest):
    client = await get_client()
    workflow_id = f"pdf-pipeline-{uuid.uuid4()}"
    
    await client.start_workflow(
        "PDFProcessingWorkflow",
        arg=PDFProcessingWorkflowInput(s3_input_path=request.s3_path),
        id=workflow_id,
        task_queue=TEMPORAL_PDF_PROCESS_TASK_QUEUE,
    )

    return ProcessPDFStartResponse(
        workflow_id=workflow_id,
    )

@app.get("/process-pdf/status/{workflow_id}", response_model=ProcessPDFStatusResponse)
async def process_pdf_status(workflow_id: str):
    client = await get_client()
    
    handle = client.get_workflow_handle(workflow_id)
    
    desc = await handle.describe()
    
    return ProcessPDFStatusResponse(
        workflow_id=workflow_id,
        status=desc.status.name
    )


@app.post("/contract-review/start")
async def start_contract_review(request: StartReviewRequest):
    
    workflow_id = f"contract-review-{uuid.uuid4()}"

    client = await get_client()

    await client.start_workflow(
        "ContractReviewWorkflow",
        arg={
            "s3_paths" : request.s3_paths,
            "max_revisions" : request.max_revisions
        },
        id=workflow_id,
        task_queue=TEMPORAL_CONTRACT_REVIEW_TASK_QUEUE,
    )

    return StartReviewResponse(workflow_id=workflow_id)


@app.get("/contract-review/{workflow_id}/status")
async def get_review_status(workflow_id: str):
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    status_result = await handle.query("get_status")
    return status_result


@app.get("/contract-review/{workflow_id}/report")
async def get_review_report(workflow_id: str):
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    report_result = await handle.query("get_report")
    return report_result


@app.post("/contract-review/assign-reviewer")
async def assign_reviewer(request: AssignRequest):
    client = await get_client()
    handle = client.get_workflow_handle(request.workflow_id)
    await handle.signal("assign_reviewer", request.name)
    return {"status": "ok", 
            "message": f"Reviewer '{request.name}' assigned."}

@app.post("/contract-review/revise")
async def submit_revise(request: ReviseRequest):
    client = await get_client()
    handle = client.get_workflow_handle(request.workflow_id)
    result = await handle.execute_update("submit_decision", args=["revise", request.feedback])
    return {"ok": True, "message": result}

@app.post("/contract-review/approve")
async def submit_approve(request: ApproveRequest):
    client = await get_client()
    handle = client.get_workflow_handle(request.workflow_id)
    result = await handle.execute_update("submit_decision", args=["approve", ""])
    return {"ok": True, "message": result}