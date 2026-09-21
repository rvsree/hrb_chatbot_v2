"""Saves uploaded files to disk and records their metadata - validated once
here so single/batch upload share the same rules; rejections are data, not raised."""

import hashlib
import json
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from src.hrb_chatbot.ai.doc_processing import pipeline
from src.hrb_chatbot.ai.doc_processing.indexing.vector_indexer import storage_chunk_ids
from src.hrb_chatbot.common.clients.db_client.langchain_vector_store import COLLECTION_NAME
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.models.documents import (
    ALLOWED_CONTENT_TYPE,
    MAX_FILE_SIZE_BYTES,
    ChunkInfoResult,
    DocumentMetadataInput,
    DocumentMetadataResult,
    DocumentUploadResult,
    VersioningInfo,
)

logger = get_logger("documents_service")

UPLOAD_DIRECTORY = Path("data/uploads")


def validate_file(upload: UploadFile, size: int) -> tuple[str, str] | None:
    """Return (message, error_code) for why this file is rejected, or None.
    error_code is stable (common/error_codes.py); message can change freely."""
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


async def save_upload(
    upload: UploadFile,
    supersedes_document_id: str | None = None,
    chunking_strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    document_metadata_override: DocumentMetadataInput | None = None,
    uploaded_by: str | None = None,
) -> DocumentUploadResult:
    """Validate, store, and record one uploaded file. Never raises.
    `supersedes_document_id` only records intent - the flip happens later,
    once this new upload successfully indexes. `uploaded_by` is the
    caller's employee_id (from the request payload's user_profile) - an
    audit field only, not part of any access-control decision."""
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

    # Same bytes = same document, regardless of filename - unlike an
    # Idempotency-Key (a request-retry cache), this catches ANY upload of identical content, any time.
    content_hash = hashlib.sha256(content).hexdigest()
    existing = await get_db_gateway().metadata_store().find_by_content_hash(content_hash)
    if existing is not None:
        logger.info(
            "Upload %r matches existing document %s (%s) by content - no new document created",
            upload.filename,
            existing["id"],
            existing["filename"],
        )
        return DocumentUploadResult(
            filename=upload.filename,
            document_id=existing["id"],
            status="duplicate",
            error=None,
            message=(
                f"Identical content already uploaded as document {existing['id']} "
                f"({existing['filename']!r}), version {existing['document_version']}. "
                "No new document was created - use that document_id to re-index if needed."
            ),
            file_size_bytes=existing["file_size_bytes"],
            versioning_info=VersioningInfo(document_version=existing["document_version"]),
        )

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
            document_id,
            upload.filename,
            str(file_path),
            size,
            content_hash,
            supersedes=supersedes_document_id,
            uploaded_by=uploaded_by,
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

    # Phase 26: index immediately - chunk, embed, write to the vector
    # store - as part of the same upload call, not a separate step.
    index_outcome = await _index_now(
        document_id, file_path,
        chunking_strategy=chunking_strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        document_metadata_override=document_metadata_override,
    )
    document_metadata = index_outcome.get("document_metadata") or {}

    return DocumentUploadResult(
        filename=upload.filename,
        document_id=document_id,
        status="uploaded",
        error=index_outcome.get("error"),
        error_code=index_outcome.get("error_code"),
        file_size_bytes=size,
        uploaded_by=uploaded_by,
        chunk_info=ChunkInfoResult(
            chunking_strategy=index_outcome.get("chunking_strategy"),
            chunk_size=index_outcome.get("chunk_size"),
            chunk_overlap=index_outcome.get("chunk_overlap"),
            action=index_outcome.get("action"),
            chunks_indexed=index_outcome.get("chunks_indexed"),
            chunks_removed=index_outcome.get("chunks_removed"),
        ),
        document_metadata=DocumentMetadataResult(**document_metadata) if document_metadata else None,
        # 0 if indexing failed - matches what the row actually holds then
        # (create_document() inserts 0; only a successful index moves it to 1+).
        versioning_info=VersioningInfo(document_version=index_outcome.get("document_version", 0)),
    )


async def _index_now(
    document_id: str,
    file_path,
    chunking_strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    document_metadata_override: DocumentMetadataInput | None = None,
) -> dict:
    """Chunk/embed/index a just-uploaded file - chunking_strategy/chunk_size/
    chunk_overlap default to .env's CHUNK_DEFAULT_* when not given. Never
    raises - a failure here still leaves the file uploaded, just not
    indexed (status becomes 'failed' on the document row)."""
    # exclude supersedes_document_id - that's handled separately, at
    # create_document() time, not part of the extraction-overridable set.
    override_dict = (
        document_metadata_override.model_dump(exclude={"supersedes_document_id"})
        if document_metadata_override
        else None
    )
    try:
        return await pipeline.index_document(
            document_id,
            str(file_path),
            chunking_strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            document_metadata_override=override_dict,
        )
    except Exception as error:
        logger.error("Indexing failed for document %s: %s: %s", document_id, type(error).__name__, error)
        await get_db_gateway().metadata_store().update_status(document_id, "failed", str(error))
        return {"error": "Upload succeeded, but indexing failed.", "error_code": error_codes.INDEXING_FAILED}


async def save_uploads(
    uploads: list[UploadFile],
    supersedes_document_id: str | None = None,
    chunking_strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    document_metadata_override: DocumentMetadataInput | None = None,
    uploaded_by: str | None = None,
) -> list[DocumentUploadResult]:
    """Validate, store, and record every uploaded file - one result per file.
    `supersedes_document_id` only applies to a single-file upload (422 on a batch);
    chunking_strategy/chunk_size/chunk_overlap/document_metadata_override apply
    to every file in the batch."""
    # One at a time, not in parallel (asyncio.gather would do that) - simpler
    # to follow, and file uploads aren't the bottleneck here.
    results = []
    for upload in uploads:
        result = await save_upload(
            upload,
            supersedes_document_id=supersedes_document_id,
            chunking_strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            document_metadata_override=document_metadata_override,
            uploaded_by=uploaded_by,
        )
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


async def delete_document(document_id: str, deleted_by: str | None = None) -> dict | None:
    """Delete one document: vectors, metadata row, uploaded file. Returns
    None if unknown (route -> 404). Vectors go first, while chunk_ids still
    exists in metadata - a failed retry can still find them; metadata is
    removed last. `deleted_by` is the caller's employee_id, pass-through
    only (not stored - the row itself is gone)."""
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
        # Phase 44 restored LlamaIndex indexing, which prefixes Pinecone ids
        # again - storage_chunk_ids() is a no-op for Chroma, real for Pinecone.
        vector_store.delete(
            collection_name=COLLECTION_NAME,
            ids=storage_chunk_ids(vector_store.PROVIDER_NAME, document_id, chunk_ids),
        )
        logger.info("Deleted %d vector(s) for document %s", len(chunk_ids), document_id)

    await metadata_store.delete_document(document_id)

    document_directory = UPLOAD_DIRECTORY / document_id
    shutil.rmtree(document_directory, ignore_errors=True)

    logger.info("Deleted document %s (%r) - %d chunk(s) removed", document_id, document["filename"], len(chunk_ids))
    return {
        "document_id": document_id,
        "filename": document["filename"],
        "chunks_removed": len(chunk_ids),
        "deleted_by": deleted_by,
    }


async def delete_all_documents(deleted_by: str | None = None) -> dict:
    """Delete every document: vectors, metadata rows, uploaded files - same
    full delete as delete_document(), just for all of them (Phase 27)."""
    documents = await list_documents()
    documents_deleted = 0
    chunks_removed = 0
    for document in documents:
        result = await delete_document(document["id"], deleted_by=deleted_by)
        if result is not None:  # already gone by the time we got here - skip, don't crash the batch
            documents_deleted += 1
            chunks_removed += result["chunks_removed"]

    logger.info("Deleted all %d document(s) - %d chunk(s) removed in total", documents_deleted, chunks_removed)
    return {"documents_deleted": documents_deleted, "chunks_removed": chunks_removed, "deleted_by": deleted_by}


async def _find_test_noise_documents(max_file_size_bytes: int) -> list[dict]:
    documents = await list_documents()
    return [document for document in documents if (document.get("file_size_bytes") or 0) < max_file_size_bytes]


async def list_test_noise_documents(max_file_size_bytes: int) -> list[dict]:
    """Preview only - which documents would delete_test_noise_documents()
    remove, without removing anything (Phase 46)."""
    return await _find_test_noise_documents(max_file_size_bytes)


async def delete_test_noise_documents(max_file_size_bytes: int, deleted_by: str | None = None) -> dict:
    """Delete every document below max_file_size_bytes - same full-delete
    semantics as delete_document(), just scoped to the test-noise subset
    instead of everything (Phase 46)."""
    documents = await _find_test_noise_documents(max_file_size_bytes)
    documents_deleted = 0
    chunks_removed = 0
    for document in documents:
        result = await delete_document(document["id"], deleted_by=deleted_by)
        if result is not None:
            documents_deleted += 1
            chunks_removed += result["chunks_removed"]

    logger.info(
        "Deleted %d test-noise document(s) (< %d bytes) - %d chunk(s) removed in total",
        documents_deleted,
        max_file_size_bytes,
        chunks_removed,
    )
    return {"documents_deleted": documents_deleted, "chunks_removed": chunks_removed, "deleted_by": deleted_by}
