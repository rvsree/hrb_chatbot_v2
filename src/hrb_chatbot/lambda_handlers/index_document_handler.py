"""Lambda entry point - SQS (triggered by an S3 ObjectCreated event) -> index
one document. A thin adapter: reads the event, downloads the object, calls
ai/doc_processing/pipeline.py's existing index_document() unchanged - see
RAG-ROADMAP.md Phase 88."""

import asyncio
import hashlib
import json
import logging
from pathlib import Path

import boto3

from src.hrb_chatbot.ai.doc_processing import pipeline
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway

TMP_DIRECTORY = Path("/tmp")


class _JsonFormatter(logging.Formatter):
    """One JSON line per log record - CloudWatch Logs Insights can then query
    fields directly, unlike the rest of this project's deliberately
    plain-text logs (see Phase 88's spec for why Lambda alone gets this)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("lambda_handlers.index_document")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


logger = _get_logger()


def _parse_s3_event(sqs_record: dict) -> tuple[str, str] | None:
    """Return (bucket, key) from one SQS message body, or None for a non-upload
    event (e.g. the s3:TestEvent S3 sends when a notification is first configured)."""
    body = json.loads(sqs_record["body"])
    if body.get("Event") == "s3:TestEvent":
        return None

    s3_info = body["Records"][0]["s3"]
    return s3_info["bucket"]["name"], s3_info["object"]["key"]


def _document_id_and_filename(key: str) -> tuple[str, str]:
    """Key convention: "{document_id}/{filename}" - the same layout
    documents_service.py already uses for local uploads under data/uploads/."""
    document_id, _, filename = key.partition("/")
    return document_id, filename or key


def _pending_overrides_kwargs(existing: dict) -> dict:
    """Phase 89: the presigned-upload route stashes chunk_info/document_metadata
    on the row it already created - unpack them into index_document()'s own
    kwargs. Returns {} if there's nothing pending (the Phase 88 direct-S3-put
    fallback path, or a retry after they were already cleared)."""
    raw = existing.get("pending_overrides")
    if not raw:
        return {}

    overrides = json.loads(raw)
    kwargs = {}
    chunk_info = overrides.get("chunk_info")
    if chunk_info:
        kwargs["chunking_strategy"] = chunk_info.get("chunking_strategy")
        kwargs["chunk_size"] = chunk_info.get("chunk_size")
        kwargs["chunk_overlap"] = chunk_info.get("chunk_overlap")
    document_metadata = overrides.get("document_metadata")
    if document_metadata:
        kwargs["document_metadata_override"] = document_metadata
    return kwargs


async def _index_one(bucket: str, key: str) -> None:
    document_id, filename = _document_id_and_filename(key)
    local_path = TMP_DIRECTORY / document_id / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3")
    s3.download_file(bucket, key, str(local_path))

    metadata_store = get_db_gateway().metadata_store()
    existing = await metadata_store.get_document(document_id)
    if existing is None:
        # No API step created this row yet - the Phase 88 direct-S3-put
        # fallback path, still useful for manual testing. Phase 89's real
        # presigned-upload endpoint always creates this row first.
        content = local_path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        await metadata_store.create_document(document_id, filename, str(local_path), len(content), content_hash)
        index_kwargs = {}
    else:
        index_kwargs = _pending_overrides_kwargs(existing)

    await metadata_store.update_status(document_id, "indexing")

    try:
        await pipeline.index_document(document_id, str(local_path), **index_kwargs)
        if index_kwargs:
            await metadata_store.set_pending_overrides(document_id, None)
    except Exception as error:
        logger.error(
            "Indexing failed for document %s (bucket=%s, key=%s): %s: %s",
            document_id, bucket, key, type(error).__name__, error,
        )
        await metadata_store.update_status(document_id, "failed", str(error))
        raise


async def _process_batch(records: list[dict]) -> list[dict]:
    """Processes every record in one SQS batch on the SAME event loop, one
    at a time - not asyncio.run() per record. Found live (Phase 88's
    concurrency test): the Redis-backed embedding cache caches its client
    on the DBGateway singleton, which outlives a single asyncio.run() call -
    a second asyncio.run() closes that loop out from under the cached
    client, raising "Event loop is closed" on every record after the
    first in a warm container. One shared loop for the whole batch fixes
    it; processing stays sequential, same as before."""
    failures = []
    for record in records:
        try:
            parsed = _parse_s3_event(record)
            if parsed is None:
                continue
            bucket, key = parsed
            await _index_one(bucket, key)
        except Exception:
            logger.error("Failed to process SQS message %s", record.get("messageId"), exc_info=True)
            failures.append({"itemIdentifier": record["messageId"]})

    return failures


def lambda_handler(event: dict, context) -> dict:
    """One invocation may carry a batch of SQS messages. Reports per-message
    failures via batchItemFailures (AWS's documented partial-batch-failure
    pattern) so one bad document retries/DLQs without blocking the rest."""
    failures = asyncio.run(_process_batch(event.get("Records", [])))
    return {"batchItemFailures": failures}
