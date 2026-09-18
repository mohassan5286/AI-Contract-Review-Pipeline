import asyncio
import os

from activities import download_pdf, extract_text, upload_text
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker
from workflow_process_pdf import PDFProcessingWorkflow

# --- Load environment variables ---
load_dotenv()

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE")
TEMPORAL_PDF_PROCESS_TASK_QUEUE = os.getenv("TEMPORAL_PDF_PROCESS_TASK_QUEUE")


# --- Helper functions ---
async def get_client():
    return await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
    )

# --- Main ---
async def main():
    client = await get_client()

    worker = Worker(
        client=client,
        task_queue=TEMPORAL_PDF_PROCESS_TASK_QUEUE,
        workflows=[PDFProcessingWorkflow],
        activities=[download_pdf, extract_text, upload_text],
    )

    print(f"Worker started. Polling task queue: '{TEMPORAL_PDF_PROCESS_TASK_QUEUE}'")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
