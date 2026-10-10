"""Sends email via AWS SES (Phase 136) - a plain function, not a Base*Client/
Gateway pair, same reasoning as s3_upload_client.py: one provider, nothing
to swap at runtime. boto3 is already a dependency (S3/Lambda use it) - no
new library for this.

Real one-time setup this code can't do by itself: a new AWS account's SES
starts in sandbox mode, which can only send to pre-verified addresses -
the SENDER identity (SES_SENDER_EMAIL) needs verifying in the SES console
before any send succeeds, sandbox or not. See docs/dev-reference/
genai_chat_workflow.md for the full note."""

import boto3
from botocore.exceptions import ClientError

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("ses_client")

DEFAULT_REGION = "us-east-1"


def send_email(recipient_email: str, subject: str, body_text: str) -> dict:
    """Returns {"sent": bool, "message": str} - never raises; a send
    failure (unverified sender, sandbox restriction, bad address) is
    reported as data, same error-handling-by-layer convention every other
    client in this project follows."""
    sender = read_setting(None, "SES_SENDER_EMAIL")
    region = read_setting(None, "AWS_REGION", DEFAULT_REGION)

    if not sender:
        return {"sent": False, "message": "SES_SENDER_EMAIL is not configured."}

    ses_client = boto3.client("ses", region_name=region)

    try:
        with log_backend_call(logger, "ses", "send_email", recipient=recipient_email):
            ses_client.send_email(
                Source=sender,
                Destination={"ToAddresses": [recipient_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body_text}},
                },
            )
    except ClientError as error:
        logger.warning("SES send to %s failed: %s", recipient_email, error)
        return {"sent": False, "message": str(error)}

    return {"sent": True, "message": f"Email sent to {recipient_email}."}
