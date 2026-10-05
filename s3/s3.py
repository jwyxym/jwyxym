import sys
import glob
import os
import time
import boto3
from botocore.config import Config
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

args = sys.argv[1:]
if len(args) != 7:
    raise SystemExit('Usage: s3.py endpoint access_key secret_key bucket key file_path content_type')

endpoint = args[0]
access_key = args[1]
secret_key = args[2]
bucket = args[3]
key = args[4]
file_path = args[5]
content_type = args[6]

if os.path.isfile(file_path):
    uploads = [(file_path, key)]
else:
    if not glob.has_magic(file_path):
        raise SystemExit(f"File not found: {file_path}")
    paths = sorted({path for path in glob.glob(file_path, recursive=True) if os.path.isfile(path)})
    if not paths:
        raise SystemExit(f"No files matched: {file_path}")
    prefix = key.rstrip("/")
    uploads = [(path, f"{prefix}/{os.path.basename(path)}" if prefix else os.path.basename(path)) for path in paths]
    seen_keys = set()
    for _, upload_key in uploads:
        if upload_key in seen_keys:
            raise SystemExit(f"Multiple files map to the same S3 key: {upload_key}")
        seen_keys.add(upload_key)


class UploadProgress:
    def __init__(self, filename):
        self.filename = filename
        self.total = os.path.getsize(filename)
        self.uploaded = 0
        self.started_at = time.time()

    def __call__(self, bytes_amount):
        self.uploaded = min(self.uploaded + bytes_amount, self.total)
        elapsed = max(time.time() - self.started_at, 0.001)
        percent = self.uploaded / self.total * 100 if self.total else 100
        speed = self.uploaded / elapsed / 1024 / 1024
        uploaded_mb = self.uploaded / 1024 / 1024
        total_mb = self.total / 1024 / 1024
        sys.stdout.write(
            f"\rUploading: {percent:6.2f}% "
            f"({uploaded_mb:.2f}/{total_mb:.2f} MB, {speed:.2f} MB/s)"
        )
        sys.stdout.flush()

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name="us-east-1",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        connect_timeout=30,
        read_timeout=300,
        retries={"max_attempts": 20, "mode": "standard"},
        request_checksum_calculation="when_required",
    )
)

try:
    for index, (upload_path, upload_key) in enumerate(uploads, start=1):
        print(f"[{index}/{len(uploads)}] {upload_path} -> s3://{bucket}/{upload_key}", flush=True)
        transfer_config = TransferConfig(
            multipart_threshold=os.path.getsize(upload_path) + 1,
            max_concurrency=1,
        )
        with open(upload_path, "rb") as file:
            s3.upload_fileobj(
                file,
                bucket,
                upload_key,
                ExtraArgs={"ContentType": content_type},
                Callback=UploadProgress(upload_path),
                Config=transfer_config,
            )
        print("\nUpload complete.", flush=True)
except ClientError as exc:
    print("\nS3 error:", exc.response.get("Error"), flush=True)
    print("Response metadata:", exc.response.get("ResponseMetadata"), flush=True)
    raise
