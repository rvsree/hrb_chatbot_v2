"""Saves uploaded files to disk and records their metadata.

Validation happens once here so single- and batch-upload share the same
rules. Rejections are returned as data (status='rejected'), not raised -
an unexpected failure becomes a 500, but a "wrong file type" is not one.
"""

import hashlib
import json
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from src.hrb_chatbot.ai.doc_processing.indexing import vector_indexer
from src.hrb_chatbot.ai.doc_processing.indexing.vector_indexer import COLLECTION_NAME
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.models.documents import (
    ALLOWED_CONTENT_TYPE,
    MAX_FILE_SIZE_BYTES,
    DocumentUploadResult,
)

logger = get_logger("documents_service")

UPLOAD_DIRECTORY = Path("data/uploads")


def validate_file(upload: UploadFile, size: int) -> tuple[str, str] | None:
    """Return (message, error_code) for why this file should be rejected, or
    None if it's fine. error_code is the stable value from common/error_codes.py -
    message can change wording freely without breaking a caller relying on it."""
    filename = upload.filename or ""

    if upload.content_type != ALLOWED_CONTENT_TYPE and not filename.lower().endswith(".pdf"):
        return f"Only PDF files are accepted, got content_type={upload.content_type!r}", error_codes.INVALID_FILE_TYPE

    if size == 0:
        return "File is empty", error_codes.EMPTY_FILE

    if size > MAX_FILE_SIZE_BYTES:
        return (
            f"File is {size} bytes, which exceeds the {MAX_FILE_SIZE_BYTES}-byte limit",
            error_codes.FILE_TOO_LARGE,
        )

    return None


async def save_upload(upload: UploadFile, supersedes_document_id: str | None = None) -> DocumentUploadResult:
    """Validate, store, and record one uploaded file. Never raises.

    `supersedes_document_id`, if given, only *records the intent* here - the
    old document isn't flipped to is_current=false until this new one
    successfully indexes (ai/doc_processing/indexing/vector_indexer.py), so
    there's never a window where neither version's content is retrievable.
    """
    try:
        content = await upload.read()
    except Exception as error:
        logger.error("Could not read upload %r: %s", upload.filename, error)
        return DocumentUploadResult(
            filename=upload.filename or "unknown",
            document_id=None,
            status="rejected",
            error=f"Could not read the uploaded file: {error}",
            error_code=error_codes.UPLOAD_READ_FAILED,
        )

    size = len(content)
    validation_failure = validate_file(upload, size)
    if validation_failure:
        message, code = validation_failure
        logger.warning("Rejected upload %r: %s", upload.filename, message)
        return DocumentUploadResult(
            filename=upload.filename or "unknown",
            document_id=None,
            status="rejected",
            error=message,
            error_code=code,
        )

    # content_hash is still recorded on the document row (useful for manual
    # lookup/audit), but no idempotency/dedup check is done against it -
    # every upload always creates a new document, even if identical content
    # was uploaded before.
    content_hash = hashlib.sha256(content).hexdigest()

    if supersedes_document_id:
        target = await get_db_gateway().metadata_store().get_document(supersedes_document_id)
        if target is None:
            logger.warning(
                "Upload %r cannot supersede unknown document %r", upload.filename, supersedes_document_id
            )
            return DocumentUploadResult(
                filename=upload.filename or "unknown",
                document_id=None,
                status="rejected",
                error=f"supersedes_document_id {supersedes_document_id!r} does not exist",
                error_code=error_codes.SUPERSEDES_TARGET_NOT_FOUND,
            )

    document_id = uuid.uuid4().hex
    document_directory = UPLOAD_DIRECTORY / document_id

    try:
        document_directory.mkdir(parents=True, exist_ok=True)
        file_path = document_directory / upload.filename
        file_path.write_bytes(content)

        await get_db_gateway().metadata_store().create_document(
            document_id, upload.filename, str(file_path), size, content_hash, supersedes=supersedes_document_id
        )
    except Exception as error:
        # A real, unexpected failure - logged with the id for traceability, but
        # still reported as a per-file rejection so the rest of the batch continues.
        logger.error("Failed to store upload %r (document %s): %s", upload.filename, document_id, error)
        return DocumentUploadResult(
            filename=upload.filename,
            document_id=None,
            status="rejected",
            error=f"Could not store the file: {error}",
            error_code=error_codes.STORAGE_FAILURE,
        )

    logger.info("Stored upload %r as document %s", upload.filename, document_id)
    return DocumentUploadResult(
        filename=upload.filename,
        document_id=document_id,
        status="uploaded",
        error=None,
        file_size_bytes=size,
        document_version=1,
    )


async def save_uploads(
    uploads: list[UploadFile], supersedes_document_id: str | None = None
) -> list[DocumentUploadResult]:
    """Validate, store, and record every uploaded file - one result per file.
    `supersedes_document_id` only applies when uploading exactly one file -
    the route rejects it (422) on a batch, where it would be ambiguous which
    file is meant to supersede it."""
    # One at a time, not in parallel (asyncio.gather would do that) - simpler
    # to follow, and file uploads aren't the bottleneck here.
    results = []
    for upload in uploads:
        result = await save_upload(upload, supersedes_document_id=supersedes_document_id)
        results.append(result)
    return results


def _parse_chunk_ids(document: dict) -> dict:
    """Turn the stored chunk_ids JSON string into a real list for the API
    response - metadata clients store it as text; this is the one place that decodes it."""
    raw = document.get("chunk_ids")
    if raw:
        document["chunk_ids"] = json.loads(raw)
    else:
        document["chunk_ids"] = None
    return document


async def list_documents() -> list[dict]:
    """Return every uploaded document's metadata, newest first."""
    documents = await get_db_gateway().metadata_store().list_documents()
    return [_parse_chunk_ids(document) for document in documents]


async def get_document(document_id: str) -> dict | None:
    """Return one document's metadata, or None if the id is unknown."""
    document = await get_db_gateway().metadata_store().get_document(document_id)
    if document is None:
        return None
    return _parse_chunk_ids(document)


async def delete_document(document_id: str) -> dict | None:
    """Delete one document completely: its vectors (if any), its metadata row,
    and its uploaded file on disk. Returns None if the id is unknown (the
    route turns that into a 404) - otherwise a summary of what was removed.

    Order matters for safety: vectors are deleted first, while the metadata
    row (and its chunk_ids - the only record of which vector ids to delete)
    still exists. If vector deletion fails partway, a retry of this same
    call can still find chunk_ids and finish the job. Only once vectors are
    confirmed gone is the metadata row removed - deleting metadata first
    would lose the one piece of information needed to find the orphaned
    vectors afterward.
    """
    gateway = get_db_gateway()
    metadata_store = gateway.metadata_store()
    document = await metadata_store.get_document(document_id)
    if document is None:
        return None

    chunk_ids = []
    if document.get("chunk_ids"):
        chunk_ids = json.loads(document["chunk_ids"])

    if chunk_ids:
        vector_store = gateway.vector_store(provider=document.get("vector_db"))
        # storage_chunk_ids(), not chunk_ids directly - Pinecone stores these
        # under a different (prefixed) id than the plain one this project
        # tracks; see its docstring for why that matters here.
        storage_ids = vector_indexer.storage_chunk_ids(vector_store.PROVIDER_NAME, document_id, chunk_ids)
        vector_store.delete(collection_name=COLLECTION_NAME, ids=storage_ids)
        logger.info("Deleted %d vector(s) for document %s", len(chunk_ids), document_id)

    await metadata_store.delete_document(document_id)

    document_directory = UPLOAD_DIRECTORY / document_id
    shutil.rmtree(document_directory, ignore_errors=True)

    logger.info("Deleted document %s (%r) - %d chunk(s) removed", document_id, document["filename"], len(chunk_ids))
    return {"document_id": document_id, "filename": document["filename"], "chunks_removed": len(chunk_ids)}
