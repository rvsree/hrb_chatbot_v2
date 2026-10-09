"""Generates presigned S3 upload URLs (Phase 89) - a plain function, not a
Base*Client/Gateway pair like the vector/metadata stores, since there's
only one storage provider here, nothing to swap at runtime."""

import boto3

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("s3_upload_client")

DEFAULT_REGION = "us-east-1"
DEFAULT_EXPIRY_SECONDS = 300


def generate_presigned_upload_url(document_id: str, filename: str, content_type: str) -> dict:
    """Returns {"upload_url": str, "expires_in_seconds": int} - the client
    PUTs the file body directly to upload_url, no AWS SDK/credentials needed
    on their end. Key convention ("{document_id}/{filename}") matches
    documents_service.py's local UPLOAD_DIRECTORY layout and the Lambda
    handler's own key-parsing (Phase 88)."""
    bucket = read_setting(None, "S3_UPLOAD_BUCKET")
    region = read_setting(None, "AWS_REGION", DEFAULT_REGION)
    expiry_seconds = int(read_setting(None, "S3_PRESIGNED_URL_EXPIRY_SECONDS", DEFAULT_EXPIRY_SECONDS))

    s3_client = boto3.client("s3", region_name=region)
    key = f"{document_id}/{filename}"

    with log_backend_call(logger, "s3", "generate_presigned_url", document_id=document_id):
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expiry_seconds,
        )

    return {"upload_url": upload_url, "expires_in_seconds": expiry_seconds}


def delete_uploaded_object(document_id: str, filename: str) -> None:
    """Best-effort S3 cleanup on document delete - same key convention as
    generate_presigned_upload_url, safe to call even if this document was
    never actually uploaded via S3 (delete_object on a missing key is a no-op)."""
    bucket = read_setting(None, "S3_UPLOAD_BUCKET")
    region = read_setting(None, "AWS_REGION", DEFAULT_REGION)
    s3_client = boto3.client("s3", region_name=region)
    key = f"{document_id}/{filename}"

    with log_backend_call(logger, "s3", "delete_object", document_id=document_id):
        s3_client.delete_object(Bucket=bucket, Key=key)
