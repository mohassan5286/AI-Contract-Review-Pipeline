import os
from dataclasses import dataclass

import boto3
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
S3_BUCKET = os.getenv("S3_BUCKET")
TEMP_DIR = os.getenv("TEMP_DIR")

os.makedirs(TEMP_DIR, exist_ok=True)

# --- Dataclass Definitions ---
@dataclass
class DownloadInput:
    s3_path: str

@dataclass
class DownloadOutput:
    local_path: str

@dataclass
class ExtractInput:
    local_pdf_path: str

@dataclass
class ExtractOutput:
    md_text: str

@dataclass
class UploadInput:
    md_text: str
    s3_path: str

@dataclass
class UploadOutput:
    s3_output_path: str

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
