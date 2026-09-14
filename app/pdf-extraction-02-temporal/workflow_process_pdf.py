from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities import download_pdf, extract_text, upload_text
    from helpers import (
        DownloadInput,
        ExtractInput,
        PDFProcessingWorkflowInput,
        PDFProcessingWorkflowOutput,
        UploadInput,
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
        )

        # --- Step 2: Extract ---
        extract_output = await workflow.execute_activity(
            extract_text,
            ExtractInput(local_pdf_path=download_output.local_path),
        )

        # --- Step 3: Upload ---
        upload_output = await workflow.execute_activity(
            upload_text,
            UploadInput(
                md_text=extract_output.md_text, 
                s3_path=params.s3_input_path
            ),
        )

        workflow.logger.info(f"Workflow Complete. Output saved to {upload_output.s3_output_path}")

        return PDFProcessingWorkflowOutput(s3_output_path=upload_output.s3_output_path)
