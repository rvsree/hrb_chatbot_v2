"""Writes chunks via LangChain's own index() + SQLRecordManager (Phase 17).
Chunk ids are `{document_id}:{chunk_index}:{content_hash}` - the hash
drives index()'s change detection. Supersede logic stays this project's own."""

import hashlib
from datetime import UTC, datetime

from langchain.indexes import SQLRecordManager
from langchain.indexes import index as run_langchain_index
from langchain_core.documents import Document

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.clients.db_client.langchain_vector_store import COLLECTION_NAME, get_vector_store
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.indexing")

# LangChain's own bookkeeping table (chunk id + content hash + last seen) -
# powers skip-if-unchanged/cleanup. Separate SQLite file from sqlite_client.py's DB.
RECORD_MANAGER_DB_URL = "sqlite:///data/record_manager.sqlite3"


def build_chunk_id(document_id: str, chunk_index: int, chunk_text: str) -> str:
    """A chunk's id: document + position + a hash of its own text -
    changing any of the three changes the id, telling index() it changed."""
    content_hash = hashlib.sha1(chunk_text.encode("utf-8")).hexdigest()[:12]
    return f"{document_id}:{chunk_index}:{content_hash}"


def _record_manager(resolved_vector_db: str) -> SQLRecordManager:
    # One namespace per vector-store backend, so switching ACTIVE_VECTOR_DB
    # never mixes up bookkeeping between two different backends.
    namespace = f"hrb_chatbot/{resolved_vector_db}/{COLLECTION_NAME}"
    manager = SQLRecordManager(namespace, db_url=RECORD_MANAGER_DB_URL)
    manager.create_schema()  # idempotent - safe to call on every write, like _ensure_table() elsewhere in this project
    return manager


def _extracted_fields(doc_type: str | None, department: str | None, doc_classification: str | None) -> dict:
    # Only include a field with a value - Pinecone's update_metadata()
    # rejects None outright (Chroma silently drops it) - "no value" means
    # the key is absent, not present-with-null.
    fields = {"doc_type": doc_type, "department": department, "doc_classification": doc_classification}
    return {key: value for key, value in fields.items() if value is not None}


def _chunks_to_documents(
    document_id: str,
    chunks: list[str],
    now: str,
    doc_type: str | None = None,
    department: str | None = None,
    doc_classification: str | None = None,
) -> list[Document]:
    # index() hashes page_content + metadata (via key_encoder below) to
    # decide a chunk's id. doc_type/department/doc_classification only come
    # from a re-index's existing_document - a first index leaves them out.
    extracted_fields = _extracted_fields(doc_type, department, doc_classification)
    return [
        Document(
            page_content=chunk_text,
            metadata={
                "document_id": document_id,
                "chunk_index": i,
                "is_current": True,
                "indexed_at": now,
                **extracted_fields,
            },
        )
        for i, chunk_text in enumerate(chunks)
    ]


async def write_chunks(
    document_id: str,
    chunks: list[str],
    vector_db: str | None = None,
    embedding_model: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict:
    gateway = get_db_gateway()
    metadata_store = gateway.metadata_store()

    vector_store, resolved_vector_db = get_vector_store(vector_db, embedding_model=embedding_model)
    record_manager = _record_manager(resolved_vector_db)

    existing_document = await metadata_store.get_document(document_id)
    if existing_document and existing_document.get("chunk_ids"):
        action = "update"
    else:
        action = "insert"

    now = datetime.now(UTC).isoformat()
    new_chunk_ids = [build_chunk_id(document_id, i, chunk) for i, chunk in enumerate(chunks)]
    # Re-index: fields already known from existing_document, go straight in.
    # First index: None, left out by _extracted_fields() - see apply_extracted_chunk_metadata().
    documents = _chunks_to_documents(
        document_id,
        chunks,
        now,
        doc_type=existing_document.get("doc_type") if existing_document else None,
        department=existing_document.get("department") if existing_document else None,
        doc_classification=existing_document.get("doc_classification") if existing_document else None,
    )

    # cleanup="incremental" deletes this document's own stale chunks in the
    # same call - source_id_key scopes that cleanup to only this document.
    index_result = run_langchain_index(
        documents,
        record_manager,
        vector_store,
        cleanup="incremental",
        source_id_key="document_id",
        key_encoder=lambda doc: build_chunk_id(document_id, doc.metadata["chunk_index"], doc.page_content),
    )
    logger.info(
        "indexing: %d added, %d updated, %d skipped (already current), %d stale removed for document %s "
        "via LangChain index() (vector_db=%s)",
        index_result["num_added"],
        index_result["num_updated"],
        index_result["num_skipped"],
        index_result["num_deleted"],
        document_id,
        resolved_vector_db,
    )

    # The embedding's own real length, not a hardcoded table - one cheap
    # embed_query() call, not len(chunks) (index() already embedded them all).
    embedding_dimension = len(vector_store.embeddings.embed_query(chunks[0])) if chunks else 0

    document_version = await metadata_store.record_successful_index(
        document_id,
        new_chunk_ids,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        vector_db=resolved_vector_db,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    # Only on this document's *first* index - no window where the old
    # version is hidden before the new one is live, no repeat on re-index.
    supersedes = existing_document.get("supersedes") if existing_document else None
    if action == "insert" and supersedes:
        old_chunk_ids = await metadata_store.mark_superseded(supersedes, superseded_by=document_id)
        if old_chunk_ids:
            # update_metadata() REPLACES the full dict, so every field must
            # be re-supplied - chunk_index is parsed from the id (document_id
            # has no colons, so segment 2 is always chunk_index).
            raw_vector_store = gateway.vector_store(provider=vector_db)
            old_metadatas = [
                {
                    "document_id": supersedes,
                    "chunk_index": int(chunk_id.split(":")[1]),
                    "is_current": False,
                    "indexed_at": now,
                }
                for chunk_id in old_chunk_ids
            ]
            raw_vector_store.update_metadata(
                collection_name=COLLECTION_NAME,
                ids=old_chunk_ids,
                metadatas=old_metadatas,
            )
            logger.info(
                "Document %s superseded by %s - %d old chunk(s) marked is_current=false",
                supersedes,
                document_id,
                len(old_chunk_ids),
            )

    return {
        "action": action,
        "chunks_indexed": index_result["num_added"] + index_result["num_updated"],
        "chunks_removed": index_result["num_deleted"],
        "embedding_dimension": embedding_dimension,
        "document_version": document_version,
        # Extra key, not part of IndexResponse (ignored there) - lets
        # pipeline.py reuse these ids without a second DB round-trip.
        "chunk_ids": new_chunk_ids,
    }


async def apply_extracted_chunk_metadata(
    document_id: str,
    chunk_ids: list[str],
    vector_db: str | None,
    doc_type: str | None,
    department: str | None,
    doc_classification: str | None,
) -> None:
    """Patch doc_type/department/doc_classification onto a document's own
    just-written chunks - only needed after a first index (a re-index
    already knows them). Same REPLACE-semantics as the supersede-flip above."""
    if not chunk_ids:
        return

    now = datetime.now(UTC).isoformat()
    extracted_fields = _extracted_fields(doc_type, department, doc_classification)
    metadatas = [
        {
            "document_id": document_id,
            "chunk_index": int(chunk_id.split(":")[1]),
            "is_current": True,
            "indexed_at": now,
            **extracted_fields,
        }
        for chunk_id in chunk_ids
    ]

    raw_vector_store = get_db_gateway().vector_store(provider=vector_db)
    raw_vector_store.update_metadata(collection_name=COLLECTION_NAME, ids=chunk_ids, metadatas=metadatas)
    logger.info(
        "Document %s: patched doc_type/department/doc_classification onto %d chunk(s) after first-index extraction",
        document_id,
        len(chunk_ids),
    )
