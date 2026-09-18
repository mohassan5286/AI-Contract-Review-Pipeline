import os
from dataclasses import dataclass

import boto3
import fitz
import pymupdf4llm
from dotenv import load_dotenv
from openai import OpenAI
from temporalio import activity

# --- Load environment variables ---
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
S3_BUCKET = os.getenv("S3_BUCKET")
TEMP_DIR = os.getenv("TEMP_DIR")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


@dataclass
class ExtractPDFInput:
    s3_path: str
    batch_size: int = 2

@dataclass
class ExtractPDFOutput:
    s3_path: str
    markdown_text: str
    page_count: int

@dataclass
class CallLLMInput:
    prompt: str

@dataclass
class CallLLMOutput:
    content: str


# --- Helper functions ---
def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=AWS_S3_ENDPOINT_URL,
        region_name=AWS_REGION,
    )

def parse_s3_path(s3_path: str):
    s3_path_no_scheme = s3_path.replace("s3://", "")
    bucket, _, key = s3_path_no_scheme.partition("/")
    return bucket, key


# --- Step 1: Download PDF from S3 and Extract Text ---
@activity.defn
async def extract_pdf(params: ExtractPDFInput) -> ExtractPDFOutput:
    bucket, key = parse_s3_path(params.s3_path)
    local_path = os.path.join(TEMP_DIR, os.path.basename(key))
    s3_client = get_s3_client()
    
    # --- 1. DOWNLOAD STAGE ---
    activity.heartbeat({"stage": "downloading", "s3_path": params.s3_path, "pages_done": 0})
    activity.logger.info(f"Downloading {params.s3_path} => {local_path}")
    s3_client.download_file(bucket, key, local_path)
    
    # --- 2. SETUP EXTRACTION ---
    doc = fitz.open(local_path)
    page_count = doc.page_count
    doc.close()
    
    activity.logger.info(f"Extracting text from {local_path} ({page_count} pages)")
    md_text = ""
    
    # --- 3. EXTRACTION STAGE ---
    for i in range(0, page_count, params.batch_size):
        chunk_end = min(i + params.batch_size, page_count)
        
        # Create a list of target page indices (0-based) for this batch
        target_pages = list(range(i, chunk_end))
        
        # Append to the string rather than overwriting
        md_text += pymupdf4llm.to_markdown(local_path, pages=target_pages)
        
        activity.heartbeat({
            "stage": "extracting",
            "s3_path": params.s3_path,
            "pages_done": chunk_end,
        })

    # --- 4. CLEANUP ---
    if os.path.exists(local_path):
        os.remove(local_path)
        activity.logger.info(f"Cleaned up temporary file: {local_path}")
    
    return ExtractPDFOutput(
        s3_path=params.s3_path, 
        markdown_text=md_text, 
        page_count=page_count
    )

# --- Step 2: Call LLM ---
@activity.defn
async def call_llm(params: CallLLMInput) -> CallLLMOutput:
    activity.logger.info("Calling LLM")
    activity.heartbeat({"stage": "calling_llm"})
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "user", "content": params.prompt},
        ]
    )
    
    return CallLLMOutput(content=response.choices[0].message.content)
