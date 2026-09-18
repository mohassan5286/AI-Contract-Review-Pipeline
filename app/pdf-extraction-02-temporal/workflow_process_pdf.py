from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import download_pdf, extract_text, upload_text
    from helpers import (
        DownloadInput,
        ExtractInput,
        UploadInput,
    )

@dataclass
class PDFProcessingWorkflowInput:
    s3_input_path: str

@dataclass
class PDFProcessingWorkflowOutput:
    s3_output_path: str

DEFAULT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=5,
)

@workflow.defn
class PDFProcessingWorkflow:
    @workflow.run
    async def run(self, params: PDFProcessingWorkflowInput) -> PDFProcessingWorkflowOutput:
        workflow.logger.info(f"Starting PDF Processing Workflow for {params.s3_input_path}")

        # --- Step 1: Download ---
        download_output = await workflow.execute_activity(
            download_pdf,
            DownloadInput(s3_path=params.s3_input_path),
            retry_policy=DEFAULT_RETRY,
            start_to_close_timeout=timedelta(minutes=5),
        )

        # --- Step 2: Extract ---
        extract_output = await workflow.execute_activity(
            extract_text,
            ExtractInput(local_pdf_path=download_output.local_path),
            retry_policy=DEFAULT_RETRY,
            start_to_close_timeout=timedelta(minutes=5),
        )

        # --- Step 3: Upload ---
        upload_output = await workflow.execute_activity(
            upload_text,
            UploadInput(
                md_text=extract_output.md_text, 
                s3_path=params.s3_input_path,
            ),
            retry_policy=DEFAULT_RETRY,
            start_to_close_timeout=timedelta(minutes=5),
        )

        workflow.logger.info(f"Workflow Complete. Output saved to {upload_output.s3_output_path}")

        return PDFProcessingWorkflowOutput(s3_output_path=upload_output.s3_output_path)
