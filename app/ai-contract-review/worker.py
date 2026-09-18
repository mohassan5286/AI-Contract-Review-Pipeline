import asyncio
import os

from activities import call_llm, extract_pdf
from child_workflow import PDFSummaryWorkflow
from dotenv import load_dotenv
from parent_workflow import ContractReviewWorkflow
from temporalio.client import Client
from temporalio.worker import Worker

# --- Load environment variables ---
load_dotenv()

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE")

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
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[ContractReviewWorkflow, PDFSummaryWorkflow],
        activities=[extract_pdf, call_llm],
    )

    print(f"Worker started. Polling task queue: '{TEMPORAL_TASK_QUEUE}'")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
