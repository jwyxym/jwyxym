import sys
import os
import time
import boto3
from botocore.config import Config
from boto3.s3.transfer import TransferConfig

args = sys.argv[1:]

endpoint = args[0]
access_key = args[1]
secret_key = args[2]
bucket = args[3]
key = args[4]
file_path = args[5]
content_type = args[6]


class UploadProgress:
    def __init__(self, filename):
        self.filename = filename
        self.total = os.path.getsize(filename)
        self.uploaded = 0
        self.started_at = time.time()

    def __call__(self, bytes_amount):
        self.uploaded += bytes_amount
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
        connect_timeout=30,
        read_timeout=300,
        retries={"max_attempts": 10, "mode": "standard"},
    )
)

transfer_config = TransferConfig(
    multipart_chunksize=16 * 1024 * 1024,
    max_concurrency=2,
)

with open(file_path, "rb") as file:
    s3.upload_fileobj(
        file,
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},
        Callback=UploadProgress(file_path),
        Config=transfer_config,
    )

print("\nUpload complete.")
