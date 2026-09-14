import logging
import os
from venv import logger

import pymupdf4llm
from helpers import (
    TEMP_DIR,
    DownloadInput,
    DownloadOutput,
    ExtractInput,
    ExtractOutput,
    UploadInput,
    UploadOutput,
    get_s3_client,
    parse_s3_path,
)
from temporalio import activity

# --- Set up logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- Step 1: Download PDF from S3 ---
@activity.defn
async def download_pdf(params: DownloadInput) -> DownloadOutput:
    bucket, key = parse_s3_path(params.s3_path)
    local_path = os.path.join(TEMP_DIR, os.path.basename(key))
    
    s3_client = get_s3_client()
    activity.logger.info(f"Downloading {params.s3_path} => {local_path}")
    s3_client.download_file(bucket, key, local_path)
    activity.logger.info(f"Downloaded {params.s3_path} => {local_path}")
    
    return DownloadOutput(local_path=local_path)

# --- Step 2: Extract text from PDF ---
@activity.defn
async def extract_text(params: ExtractInput) -> ExtractOutput:
    activity.logger.info(f"Extracting text from {params.local_pdf_path}")
    md_text = pymupdf4llm.to_markdown(params.local_pdf_path)
    activity.logger.info(f"Extracted text from {params.local_pdf_path}")
    
    # Clean up the local PDF file immediately after extracting to save disk space
    if os.path.exists(params.local_pdf_path):
        os.remove(params.local_pdf_path)
        activity.logger.info(f"Cleaned up temporary file: {params.local_pdf_path}")
        
    return ExtractOutput(md_text=md_text)

# --- Step 3: Upload text to S3 ---
@activity.defn
async def upload_text(params: UploadInput) -> UploadOutput:
    bucket, key = parse_s3_path(params.s3_path)
    key_md = key.replace(".pdf", ".md")

    s3_client = get_s3_client()
    s3_output_path = f"s3://{bucket}/{key_md}"
    
    activity.logger.info(f"Uploading {key_md} => {s3_output_path}")
    s3_client.put_object(
        Bucket=bucket,
        Key=key_md,
        Body=params.md_text.encode("utf-8"),
        ContentType="text/markdown",
    )
    activity.logger.info(f"Uploaded {key_md} => {s3_output_path}")

    return UploadOutput(s3_output_path=s3_output_path)
