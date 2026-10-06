#!/usr/bin/env python
"""Runs the Phase 88 Lambda's own logic as a local, long-running worker
instead of real AWS Lambda compute - S3 and SQS stay real, only the
"compute" moves to this machine. Lets the whole presigned-upload -> S3 ->
SQS -> index flow (Phases 88-89) be developed and tested against real,
free-tier AWS resources without ever building/pushing a Docker image or
paying for a real Lambda invocation during iteration - the same
real-AWS-SDK-from-localhost pattern as any app that connects out to S3/
SQS/Postgres from a developer's own machine, not an emulator.

Deploying for real still means pushing to the Lambda (now automated via
.github/workflows/deploy-lambda.yml) - this script is for local
iteration only, never meant to replace that.

**Before running this: disable the real Lambda's SQS trigger, or it will
race this script for the same messages** - confirmed live (2026-10-06):
both consumers poll the identical real queue, and AWS's own event source
mapping is almost always faster, silently stealing messages meant for
local testing (and writing to the real Postgres/Pinecone instead of your
local SQLite/Chroma) with zero error on either side.
    aws lambda update-event-source-mapping --uuid <uuid> --no-enabled --region us-east-1
Also confirmed live: AWS reports the mapping's State as "Disabled"
before its poller fleet has actually fully stopped - there's a real
drain delay (minutes, not seconds) during which it can still grab a
message even after the API says Disabled. Wait a few minutes after
disabling before relying on exclusive local delivery. Get the UUID with
`aws lambda list-event-source-mappings --function-name
hrb-chatbot-index-document --region us-east-1`. Re-enable the same way
(`--enabled` instead of `--no-enabled`) once done, or production stops
processing real uploads.

Usage (from the repo root, with AWS credentials already configured -
run as a module, not a plain script, so `from src.hrb_chatbot...`
resolves the same way it does everywhere else in this project):
    .venv\\Scripts\\python.exe -m scripts.run_local_lambda_worker
Stop with Ctrl+C - in-flight messages are simply left for SQS to
redeliver, same as a real Lambda crashing mid-batch would."""

import json
import sys

import boto3

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.lambda_handlers.index_document_handler import lambda_handler

logger = get_logger("run_local_lambda_worker")

DEFAULT_REGION = "us-east-1"
WAIT_TIME_SECONDS = 20  # SQS long polling - free, and avoids a tight empty-queue loop
MAX_MESSAGES_PER_POLL = 5  # matches the real event source mapping's own batch size


def _queue_url() -> str:
    queue_url = read_setting(None, "SQS_INGEST_QUEUE_URL")
    if not queue_url:
        print("SQS_INGEST_QUEUE_URL is not set in .env - see RAG-ROADMAP.md Phase 88 for the real queue URL.")
        sys.exit(1)
    return queue_url


def _poll_once(sqs_client, queue_url: str) -> None:
    response = sqs_client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=MAX_MESSAGES_PER_POLL,
        WaitTimeSeconds=WAIT_TIME_SECONDS,
    )
    messages = response.get("Messages", [])
    if not messages:
        return

    logger.info("Received %d message(s) from the real SQS queue", len(messages))

    event = {
        "Records": [
            {"messageId": message["MessageId"], "body": message["Body"]}
            for message in messages
        ]
    }
    result = lambda_handler(event, context=None)
    failed_message_ids = {failure["itemIdentifier"] for failure in result["batchItemFailures"]}

    for message in messages:
        if message["MessageId"] in failed_message_ids:
            logger.warning("Leaving message %s for SQS to redeliver (processing failed)", message["MessageId"])
            continue
        sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
        logger.info("Acked (deleted) message %s - processed successfully", message["MessageId"])


def main() -> None:
    region = read_setting(None, "AWS_REGION", DEFAULT_REGION)
    queue_url = _queue_url()
    sqs_client = boto3.client("sqs", region_name=region)

    logger.info("Polling %s - Ctrl+C to stop", queue_url)
    try:
        while True:
            _poll_once(sqs_client, queue_url)
    except KeyboardInterrupt:
        logger.info("Stopped - any in-flight message is simply left for SQS to redeliver later.")


if __name__ == "__main__":
    main()
