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

**Points at its own separate dev bucket/queue, not production's** -
`.env`'s S3_UPLOAD_BUCKET`/`SQS_INGEST_QUEUE_URL` are
`hrb-chatbot-kb-uploads-dev`/`hrb-chatbot-ingest-queue-dev` (-dev suffix
on both), completely separate AWS resources from the real
`hrb-chatbot-kb-uploads`/`hrb-chatbot-ingest-queue` App Runner and the
real Lambda use. This is the fix for a real bug found and then properly
root-caused on 2026-10-06: an earlier version of this script pointed at
the SAME real queue production uses, and the real deployed Lambda's own
SQS trigger almost always won the race for each message (confirmed:
disabling the event source mapping wasn't even reliable - AWS reports
"Disabled" before its poller fleet has actually drained, so even a
disable-then-retry could still lose). Giving local testing its own
queue/bucket removes the race entirely, rather than working around it -
there is nothing to disable or wait for now; this script and the real
Lambda simply never compete for the same message.

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
