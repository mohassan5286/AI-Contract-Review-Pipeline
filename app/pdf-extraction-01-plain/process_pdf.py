import logging
import os
import sys

import boto3
import pymupdf4llm
from dotenv import load_dotenv

# --- Set up logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Load environment variables ---
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
S3_BUCKET = os.getenv("S3_BUCKET")
TEMP_DIR = os.getenv("TEMP_DIR")

os.makedirs(TEMP_DIR, exist_ok=True)

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

# --- Step 1: Download PDF from S3 ---
def download_pdf(s3_path: str) -> str:
    bucket, key = parse_s3_path(s3_path)
    local_path = os.path.join(TEMP_DIR, os.path.basename(key))
    
    s3_client = get_s3_client()
    logger.info(f"Downloading {s3_path} => {local_path}")
    s3_client.download_file(bucket, key, local_path)
    logger.info(f"Downloaded {s3_path} => {local_path}")
    
    return local_path

# --- Step 2: Extract text from PDF ---
def extract_text(local_pdf_path: str) -> str:
    logger.info(f"Extracting text from {local_pdf_path}")
    md_text = pymupdf4llm.to_markdown(local_pdf_path)
    logger.info(f"Extracted text from {local_pdf_path}")
    return md_text

# --- Step 3: Upload text to S3 ---
def upload_text(md_text: str, s3_path: str):
    bucket, key = parse_s3_path(s3_path)
    key_md = key.replace(".pdf", ".md")

    s3_client = get_s3_client()
    s3_output_path = f"s3://{bucket}/{key_md}"
    logger.info(f"Uploading {key_md} => {s3_output_path}")
    s3_client.put_object(
        Bucket=bucket,
        Key=key_md,
        Body=md_text.encode("utf-8"),
        ContentType="text/markdown",
    )
    logger.info(f"Uploaded {key_md} => {s3_output_path}")

    return s3_output_path

# --- Main processing function ---
def process_pdf(s3_path: str):
    local_pdf_path = download_pdf(s3_path)
    md_text = extract_text(local_pdf_path)
    os.remove(local_pdf_path)
    return upload_text(md_text, s3_path)

# --- Run the main processing function ---
if __name__ == "__main__":
    output_s3 = process_pdf(sys.argv[1])
    logger.info(f"\nDone! Markdown saved to: {output_s3}")
