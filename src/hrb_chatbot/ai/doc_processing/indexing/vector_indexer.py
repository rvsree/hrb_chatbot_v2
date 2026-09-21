"""Writes chunks into a vector index built with LlamaIndex's VectorStoreIndex
(workshop Module 3, Phase 44) - insert/re-index against ChromaDB/Pinecone.
Full design rationale: docs/RAG-ROADMAP.md's Phase 44 entry."""

import json
from datetime import UTC, datetime

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.vector_stores.pinecone import PineconeVectorStore

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.clients.db_client.langchain_vector_store import COLLECTION_NAME
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.indexing")


def build_chunk_ids(document_id: str, chunk_count: int) -> list[str]:
    return [f"{document_id}:{i}" for i in range(chunk_count)]


def storage_chunk_ids(provider_name: str, document_id: str, chunk_ids: list[str]) -> list[str]:
    """Pinecone prefixes stored ids with f"{document_id}#" (LlamaIndex's
    doing, see RAG-ROADMAP.md's Phase 44 entry) - Chroma does not."""
    if provider_name == "pinecone":
        return [f"{document_id}#{chunk_id}" for chunk_id in chunk_ids]
    return chunk_ids


def _llama_vector_index(vector_store_client) -> VectorStoreIndex:
    # Wraps this project's already-connected ChromaDB/Pinecone client's raw
    # collection/index object in LlamaIndex's own vector store class, so
    # LlamaIndex writes into the exact same physical collection/namespace
    # this project's other code (delete, health checks) already uses -
    # not a second, separate store.
    if vector_store_client.PROVIDER_NAME == "pinecone":
        pinecone_index = vector_store_client.get_index()
        llama_vector_store = PineconeVectorStore(pinecone_index=pinecone_index, namespace=COLLECTION_NAME)
    else:
        chroma_collection = vector_store_client.get_collection(COLLECTION_NAME)
        llama_vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    return VectorStoreIndex.from_vector_store(llama_vector_store)


def _extracted_fields(doc_type: str | None, department: str | None, doc_classification: str | None) -> dict:
    # Only include a field with a value - Pinecone's update_metadata()
    # rejects None outright (Chroma silently drops it) - "no value" means
    # the key is absent, not present-with-null.
    fields = {"doc_type": doc_type, "department": department, "doc_classification": doc_classification}
    return {key: value for key, value in fields.items() if value is not None}


def _build_nodes(
    document_id: str, chunk_ids: list[str], chunks: list[str], embeddings: list[list[float]], metadatas: list[dict]
) -> list[TextNode]:
    # Embedding pre-computed, attached directly. document_id goes via the
    # SOURCE relationship, not node.metadata - see RAG-ROADMAP.md's Phase
    # 44 entry for why (a reserved-key collision otherwise).
    nodes = []
    for chunk_id, text, embedding, metadata in zip(chunk_ids, chunks, embeddings, metadatas, strict=True):
        node = TextNode(id_=chunk_id, text=text, embedding=embedding, metadata=metadata)
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=document_id)
        nodes.append(node)
    return nodes


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
    metadata_store = gateway.metadata_store()
    vector_store_client = gateway.vector_store(provider=vector_db)
    resolved_vector_db = vector_store_client.PROVIDER_NAME

    existing_document = await metadata_store.get_document(document_id)
    if existing_document and existing_document.get("chunk_ids"):
        action = "update"
        old_chunk_ids = json.loads(existing_document["chunk_ids"])
    else:
        action = "insert"
        old_chunk_ids = []

    now = datetime.now(UTC).isoformat()
    new_chunk_ids = build_chunk_ids(document_id, len(chunks))
    # doc_type/department/doc_classification only come from a re-index's
    # existing_document - a first index leaves them out (see
    # apply_extracted_chunk_metadata(), which patches them in afterward).
    extracted_fields = _extracted_fields(
        existing_document.get("doc_type") if existing_document else None,
        existing_document.get("department") if existing_document else None,
        existing_document.get("doc_classification") if existing_document else None,
    )
    metadatas = [
        {"chunk_index": i, "is_current": True, "indexed_at": now, **extracted_fields} for i in range(len(chunks))
    ]

    # Delete old chunks BEFORE inserting new ones - insert_nodes() uses a
    # plain add(), not upsert, and silently no-ops on a reused id
    # (RAG-ROADMAP.md's Phase 44 entry has the full story).
    if old_chunk_ids:
        vector_store_client.delete(
            collection_name=COLLECTION_NAME,
            ids=storage_chunk_ids(resolved_vector_db, document_id, old_chunk_ids),
        )

    llama_index = _llama_vector_index(vector_store_client)
    nodes = _build_nodes(document_id, new_chunk_ids, chunks, embeddings, metadatas)
    llama_index.insert_nodes(nodes)

    # Stale = existed before but not in the fresh set - reported for the
    # caller, not a separate delete call (already handled above).
    stale_ids = [chunk_id for chunk_id in old_chunk_ids if chunk_id not in new_chunk_ids]
    if stale_ids:
        logger.info("Removed %d stale chunk(s) for document %s", len(stale_ids), document_id)

    # The embeddings this call was given, not a fresh embed call - Module 1's
    # own explicit step (pipeline.py) already computed these once.
    embedding_dimension = len(embeddings[0]) if embeddings else 0

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
        superseded_chunk_ids = await metadata_store.mark_superseded(supersedes, superseded_by=document_id)
        if superseded_chunk_ids:
            # update_metadata() REPLACES the full dict, so every field must
            # be re-supplied - chunk_index is parsed from the id (document_id
            # has no colons, so segment 2 is always chunk_index).
            old_metadatas = [
                {"chunk_index": int(chunk_id.split(":")[1]), "is_current": False, "indexed_at": now}
                for chunk_id in superseded_chunk_ids
            ]
            vector_store_client.update_metadata(
                collection_name=COLLECTION_NAME,
                ids=storage_chunk_ids(resolved_vector_db, supersedes, superseded_chunk_ids),
                metadatas=old_metadatas,
            )
            logger.info(
                "Document %s superseded by %s - %d old chunk(s) marked is_current=false",
                supersedes,
                document_id,
                len(superseded_chunk_ids),
            )

    logger.info(
        "indexing: wrote %d chunk(s) for document %s via LlamaIndex VectorStoreIndex (vector_db=%s)",
        len(chunks),
        document_id,
        resolved_vector_db,
    )

    return {
        "action": action,
        "chunks_indexed": len(chunks),
        "chunks_removed": len(stale_ids),
        "embedding_dimension": embedding_dimension,
        "document_version": document_version,
        # Extra key, not part of a return contract elsewhere - lets
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
        {"chunk_index": int(chunk_id.split(":")[1]), "is_current": True, "indexed_at": now, **extracted_fields}
        for chunk_id in chunk_ids
    ]

    vector_store_client = get_db_gateway().vector_store(provider=vector_db)
    vector_store_client.update_metadata(
        collection_name=COLLECTION_NAME,
        ids=storage_chunk_ids(vector_store_client.PROVIDER_NAME, document_id, chunk_ids),
        metadatas=metadatas,
    )
    logger.info(
        "Document %s: patched doc_type/department/doc_classification onto %d chunk(s) after first-index extraction",
        document_id,
        len(chunk_ids),
    )
