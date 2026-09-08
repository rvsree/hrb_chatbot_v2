"""Saves uploaded files to disk and records their metadata.

Validation happens here, once, so the single- and batch-upload cases (the
same endpoint - a single upload is just a list of one) get identical rules:
PDF only, not empty, not too large. A rejected file is reported with a clear
reason and does not stop the rest of the batch from being stored - see
models/documents.py's docstring for why that matters.

Errors are returned as data here (a DocumentUploadResult with status
'rejected'), not raised - the router turns an unexpected failure into a 500
if one ever occurs, but an ordinary "wrong file type" is not exceptional,
it's an expected outcome the caller needs to see per file.
"""

import json
import uuid
from pathlib import Path

from fastapi import UploadFile

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.models.documents import (
    ALLOWED_CONTENT_TYPE,
    MAX_FILE_SIZE_BYTES,
    DocumentUploadResult,
)

logger = get_logger("documents_service")

UPLOAD_DIRECTORY = Path("data/uploads")


def validate_file(upload: UploadFile, size: int) -> str | None:
    """Return why this file should be rejected, or None if it's fine."""
    filename = upload.filename or ""

    if upload.content_type != ALLOWED_CONTENT_TYPE and not filename.lower().endswith(".pdf"):
        return f"Only PDF files are accepted, got content_type={upload.content_type!r}"

    if size == 0:
        return "File is empty"

    if size > MAX_FILE_SIZE_BYTES:
        return f"File is {size} bytes, which exceeds the {MAX_FILE_SIZE_BYTES}-byte limit"

    return None


async def save_upload(upload: UploadFile) -> DocumentUploadResult:
    """Validate, store, and record one uploaded file. Never raises."""
    try:
        content = await upload.read()
    except Exception as error:
        logger.error("Could not read upload %r: %s", upload.filename, error)
        return DocumentUploadResult(
            filename=upload.filename or "unknown",
            document_id=None,
            status="rejected",
            error=f"Could not read the uploaded file: {error}",
        )

    size = len(content)
    error = validate_file(upload, size)
    if error:
        logger.warning("Rejected upload %r: %s", upload.filename, error)
        return DocumentUploadResult(
            filename=upload.filename or "unknown", document_id=None, status="rejected", error=error
        )

    document_id = uuid.uuid4().hex
    document_directory = UPLOAD_DIRECTORY / document_id

    try:
        document_directory.mkdir(parents=True, exist_ok=True)
        file_path = document_directory / upload.filename
        file_path.write_bytes(content)

        await get_db_gateway().metadata_store().create_document(document_id, upload.filename, str(file_path))
    except Exception as error:
        # A disk or database failure here is a real, unexpected problem - log it with
        # the id so it's traceable, but still report it as a per-file rejection rather
        # than raising, so the rest of a batch upload is unaffected.
        logger.error("Failed to store upload %r (document %s): %s", upload.filename, document_id, error)
        return DocumentUploadResult(
            filename=upload.filename,
            document_id=None,
            status="rejected",
            error=f"Could not store the file: {error}",
        )

    logger.info("Stored upload %r as document %s", upload.filename, document_id)
    return DocumentUploadResult(
        filename=upload.filename, document_id=document_id, status="uploaded", error=None
    )


async def save_uploads(uploads: list[UploadFile]) -> list[DocumentUploadResult]:
    """Validate, store, and record every uploaded file - one result per file."""
    return [await save_upload(upload) for upload in uploads]


def _parse_chunk_ids(document: dict) -> dict:
    """Turn the stored chunk_ids JSON string into a real list for the API
    response - the metadata clients store it as text (see
    base_metadata_client.py), so this is the one place that decodes it."""
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
