"""Writes chunks and embeddings into whichever vector store RAG_VECTOR_DB
selects, correctly handling both a document's first index (insert) and a
re-index (update).

Why "update" needs more than just upserting by id
------------------------------------------------------
Chunk ids are deterministic - f"{document_id}:{chunk_index}" - so upserting
the same document's chunks a second time naturally *overwrites* the ones
that still exist. But if the document changed and now produces fewer chunks
than it did last time (a shorter revision, say), the old chunks past the
new count are never touched by that upsert - they'd sit in the vector store
forever, still returned by a similarity search, pointing at content that no
longer exists. So a re-index has to know exactly which ids existed before,
delete whichever of those aren't part of the new set, and only then is the
document's indexed state actually replaced rather than merely extended.

That "which ids existed before" list is kept in the metadata store
(SQLite/Postgres's documents.chunk_ids column - see
common/clients/db_client/base_metadata_client.py), not the vector store,
because neither ChromaDB nor Pinecone has a concept of "every chunk
belonging to one document" to ask for - only "one chunk by its id".
"""

import json

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.indexing")

# One collection/namespace for the whole knowledge base - see
# ChromaDBClient/PineconeClient's own docstrings for what this name means on
# each backend (a Chroma collection; a Pinecone namespace within one index).
COLLECTION_NAME = "hrb_chatbot_kb"


def build_chunk_ids(document_id: str, chunk_count: int) -> list[str]:
    """Deterministic ids: same document + same chunk position = same id,
    which is exactly what makes upsert-as-update work for the chunks that
    still exist across a re-index."""
    return [f"{document_id}:{i}" for i in range(chunk_count)]


async def write_chunks(
    document_id: str, chunks: list[str], embeddings: list[list[float]], vector_db: str | None = None
) -> dict:
    """Insert or update one document's chunks in the selected vector store.

    `vector_db` overrides RAG_VECTOR_DB for this one call - see
    db_gateway.vector_store().

    Known limitation, not solved here: if a document was indexed to store A
    and this call indexes it to store B, the chunk_ids recorded afterward
    only describe store B - store A's chunks are neither cleaned up nor
    tracked any more. This is safe as long as one document is always
    indexed to the same store; switching stores per-document is not this
    feature's job.

    Returns {"action": "insert" | "update", "chunks_indexed": N, "chunks_removed": N}.
    """
    gateway = get_db_gateway()
    vector_store = gateway.vector_store(provider=vector_db)
    # Whichever metadata store RAG_METADATA_STORE selects - matches
    # documents_service.py's own choice, so chunk_ids written here are read
    # back from the same place. Independent of RAG_VECTOR_DB, which is only
    # about the vector store.
    metadata_store = gateway.metadata_store()

    existing_document = await metadata_store.get_document(document_id)
    previous_chunk_ids: list[str] = []
    if existing_document and existing_document.get("chunk_ids"):
        previous_chunk_ids = json.loads(existing_document["chunk_ids"])

    action = "update" if previous_chunk_ids else "insert"
    new_chunk_ids = build_chunk_ids(document_id, len(chunks))
    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]

    vector_store.upsert(
        collection_name=COLLECTION_NAME,
        ids=new_chunk_ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # Only the ids that existed before but are NOT part of the fresh set are
    # stale - everything still in new_chunk_ids was just overwritten by the
    # upsert above, not left behind.
    stale_ids = [chunk_id for chunk_id in previous_chunk_ids if chunk_id not in new_chunk_ids]
    if stale_ids:
        vector_store.delete(collection_name=COLLECTION_NAME, ids=stale_ids)
        logger.info("Removed %d stale chunk(s) for document %s", len(stale_ids), document_id)

    await metadata_store.set_chunk_ids(document_id, new_chunk_ids)

    return {"action": action, "chunks_indexed": len(chunks), "chunks_removed": len(stale_ids)}
