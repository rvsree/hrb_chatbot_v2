"""Writes chunks and embeddings into the vector store RAG_VECTOR_DB selects,
handling both a document's first index (insert) and a re-index (update)."""

import json
from datetime import UTC, datetime

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.indexing")

COLLECTION_NAME = "hrb_chatbot_kb"

def build_chunk_ids(document_id: str, chunk_count: int) -> list[str]:
    """Deterministic ids: same document + same chunk position = same id,
    which is what makes upsert-as-update work across a re-index."""
    return [f"{document_id}:{i}" for i in range(chunk_count)]


async def write_chunks(
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    vector_db: str | None = None,
    embedding_model: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict:
    gateway = get_db_gateway()
    vector_store = gateway.vector_store(provider=vector_db)
    metadata_store = gateway.metadata_store()

    # vector_store.PROVIDER_NAME is the *resolved* backend name (e.g. "chromadb"),
    # not the possibly-None vector_db override above - this is what gets persisted,
    # so a reader of the document's metadata later knows which store was actually used.
    resolved_vector_db = vector_store.PROVIDER_NAME
    # The embedding's own length, not a hardcoded model->dimension table - stays
    # correct for any model, including ones not in any lookup table written today.
    embedding_dimension = len(embeddings[0]) if embeddings else 0

    existing_document = await metadata_store.get_document(document_id)
    previous_chunk_ids: list[str] = []
    if existing_document and existing_document.get("chunk_ids"):
        previous_chunk_ids = json.loads(existing_document["chunk_ids"])

    if previous_chunk_ids:
        action = "update"
    else:
        action = "insert"
    new_chunk_ids = build_chunk_ids(document_id, len(chunks))
    now = datetime.now(UTC).isoformat()
    metadatas = [
        {"document_id": document_id, "chunk_index": i, "is_current": True, "indexed_at": now}
        for i in range(len(chunks))
    ]

    vector_store.upsert(
        collection_name=COLLECTION_NAME,
        ids=new_chunk_ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # Stale = existed before but not in the fresh set; anything still in
    # new_chunk_ids was just overwritten by the upsert above, not left behind.
    stale_ids = []
    for chunk_id in previous_chunk_ids:
        if chunk_id not in new_chunk_ids:
            stale_ids.append(chunk_id)
    if stale_ids:
        vector_store.delete(collection_name=COLLECTION_NAME, ids=stale_ids)
        logger.info("Removed %d stale chunk(s) for document %s", len(stale_ids), document_id)

    document_version = await metadata_store.record_successful_index(
        document_id,
        new_chunk_ids,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        vector_db=resolved_vector_db,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    # Propagate the supersede recorded at upload time - only on this
    # document's *first* successful index, so there's never a window where
    # the old version is hidden before the new one is actually live, and so
    # a later re-index of the same document doesn't repeat the flip.
    supersedes = existing_document.get("supersedes") if existing_document else None
    if action == "insert" and supersedes:
        old_chunk_ids = await metadata_store.mark_superseded(supersedes, superseded_by=document_id)
        if old_chunk_ids:
            # Metadata is reconstructed, not fetched, since chunk_id already encodes
            # document_id/chunk_index deterministically ("document_id:chunk_index") -
            # see update_metadata()'s contract for why every field must be given.
            # The old chunk's original indexed_at is not preserved here (replaced
            # with "when it was superseded" instead) - acceptable since a
            # superseded chunk is excluded from retrieval either way.
            old_metadatas = [
                {"document_id": supersedes, "chunk_index": index, "is_current": False, "indexed_at": now}
                for index in range(len(old_chunk_ids))
            ]
            vector_store.update_metadata(
                collection_name=COLLECTION_NAME, ids=old_chunk_ids, metadatas=old_metadatas
            )
            logger.info(
                "Document %s superseded by %s - %d old chunk(s) marked is_current=false",
                supersedes,
                document_id,
                len(old_chunk_ids),
            )

    return {
        "action": action,
        "chunks_indexed": len(chunks),
        "chunks_removed": len(stale_ids),
        "embedding_dimension": embedding_dimension,
        "document_version": document_version,
    }
