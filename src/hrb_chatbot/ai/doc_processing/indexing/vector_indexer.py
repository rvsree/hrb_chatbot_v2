"""Writes chunks into a vector index built with LlamaIndex's VectorStoreIndex
(workshop Module 3), against whichever vector store RAG_VECTOR_DB selects -
ChromaDB or Pinecone - handling both a document's first index (insert) and
a re-index (update).

LlamaIndex only does the "write the chunks in as vectors" part here
(index.insert_nodes()). Everything around it - which ids are new vs. stale,
deleting stale chunks, flipping a superseded document's chunks to
is_current=false - stays this project's own logic, using the same
BaseVectorDBClient.delete()/update_metadata() calls as before, since that
logic has nothing to do with which library writes the vectors themselves.
"""

import json
from datetime import UTC, datetime

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.vector_stores.pinecone import PineconeVectorStore

from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.indexing")

COLLECTION_NAME = "hrb_chatbot_kb"

def build_chunk_ids(document_id: str, chunk_count: int) -> list[str]:
    """Deterministic ids: same document + same chunk position = same id,
    which is what makes upsert-as-update work across a re-index."""
    return [f"{document_id}:{i}" for i in range(chunk_count)]


def storage_chunk_ids(provider_name: str, document_id: str, chunk_ids: list[str]) -> list[str]:
    """The id(s) actually stored in the vector backend for these chunks - not
    always the same string as build_chunk_ids()'s plain deterministic ids.

    Needed because LlamaIndex's PineconeVectorStore.add() silently prefixes
    every stored id with f"{ref_doc_id}#" whenever a node has a SOURCE
    relationship set - which _build_nodes() always sets, since that's also
    what makes document_id metadata populate correctly (see its docstring).
    Confirmed live while building this: a raw delete()/update_metadata()
    call using the plain id silently matches nothing on Pinecone (no error -
    Pinecone just no-ops on an id that doesn't exist), which would have left
    every "deleted" stale chunk and every "flipped" superseded chunk still
    sitting there, un-removed/un-flipped, forever. ChromaVectorStore does
    not do this - Chroma's stored ids match the plain chunk_ids exactly."""
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


def _build_nodes(
    document_id: str, chunk_ids: list[str], chunks: list[str], embeddings: list[list[float]], metadatas: list[dict]
) -> list[TextNode]:
    # One TextNode per chunk, embedding already computed (ai/doc_processing/
    # embedding/embedding_generator.py) and attached directly - LlamaIndex
    # only calls its own embed model for a node that doesn't already have one.
    #
    # document_id is deliberately NOT put in node.metadata - LlamaIndex's own
    # ChromaVectorStore.add() reserves the metadata keys "document_id",
    # "doc_id", and "ref_doc_id" for its own use (derived from the node's
    # SOURCE relationship below) and silently OVERWRITES a same-named custom
    # metadata field with its own (here, unset) value - confirmed live while
    # building this: passing document_id via node.metadata directly made
    # every stored chunk's document_id read back as the literal string
    # "None". Setting the relationship instead makes LlamaIndex populate
    # document_id/doc_id/ref_doc_id correctly, with the real value.
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
    # document_id is NOT included here - see _build_nodes()'s docstring for
    # why it's passed separately and set via the node's SOURCE relationship
    # instead of as a plain metadata field.
    metadatas = [{"chunk_index": i, "is_current": True, "indexed_at": now} for i in range(len(chunks))]

    llama_index = _llama_vector_index(vector_store)
    nodes = _build_nodes(document_id, new_chunk_ids, chunks, embeddings, metadatas)
    llama_index.insert_nodes(nodes)

    # Stale = existed before but not in the fresh set; anything still in
    # new_chunk_ids was just overwritten by the upsert above, not left behind.
    stale_ids = []
    for chunk_id in previous_chunk_ids:
        if chunk_id not in new_chunk_ids:
            stale_ids.append(chunk_id)
    if stale_ids:
        vector_store.delete(
            collection_name=COLLECTION_NAME,
            ids=storage_chunk_ids(resolved_vector_db, document_id, stale_ids),
        )
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
                collection_name=COLLECTION_NAME,
                ids=storage_chunk_ids(resolved_vector_db, supersedes, old_chunk_ids),
                metadatas=old_metadatas,
            )
            logger.info(
                "Document %s superseded by %s - %d old chunk(s) marked is_current=false",
                supersedes,
                document_id,
                len(old_chunk_ids),
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
    }
