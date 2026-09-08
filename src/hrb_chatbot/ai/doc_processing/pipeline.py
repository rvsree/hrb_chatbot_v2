"""Orchestrates turning one stored PDF into indexed, searchable chunks.

The three steps below now call real implementations - see
ai/doc_processing/chunking/text_chunker.py, ai/doc_processing/embedding/
embedding_generator.py, and ai/doc_processing/indexing/vector_indexer.py
for how each one actually works and why. This file stays a thin
orchestrator: it names the sequence, it doesn't contain the logic.

Every parameter below defaults to the .env-configured default (RAG_VECTOR_DB,
OPENAI_EMBED_MODEL, text_chunker's own DEFAULT_CHUNK_SIZE/OVERLAP) when not
given - see models/documents.py's IndexRequest, which is what
POST /rag/documents/{id}/index actually accepts, for the per-call override
this exists to support.
"""

from src.hrb_chatbot.ai.doc_processing.chunking.text_chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_text,
    extract_text_from_pdf,
)
from src.hrb_chatbot.ai.doc_processing.embedding.embedding_generator import generate_embeddings
from src.hrb_chatbot.ai.doc_processing.indexing.vector_indexer import write_chunks
from src.hrb_chatbot.common.clients.llm_client.openai_client import OpenAIEmbeddingClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.pipeline")


def chunk_document(
    file_path: str, chunk_size: int | None = None, chunk_overlap: int | None = None
) -> list[str]:
    """Extract a PDF's text and split it into overlapping chunks."""
    text = extract_text_from_pdf(file_path)
    return chunk_text(
        text,
        chunk_size=chunk_size or DEFAULT_CHUNK_SIZE,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else DEFAULT_CHUNK_OVERLAP,
    )


def embed_chunks(chunks: list[str], embedding_model: str | None = None) -> list[list[float]]:
    """Turn each chunk into an embedding vector, same order as chunks."""
    return generate_embeddings(chunks, embedding_model=embedding_model)


async def index_chunks(
    document_id: str, chunks: list[str], embeddings: list[list[float]], vector_db: str | None = None
) -> dict:
    """Write chunks+embeddings into the configured vector store.

    Handles both a document's first index (insert) and a re-index (update -
    a document's stale chunks from a previous index are removed, not just
    overwritten where ids happen to still match) - see vector_indexer.py.
    """
    return await write_chunks(document_id, chunks, embeddings, vector_db=vector_db)


async def index_document(
    document_id: str,
    file_path: str,
    vector_db: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model: str | None = None,
) -> dict:
    """Run the full pipeline for one stored document: chunk, embed, index.

    Called by POST /rag/documents/{id}/index once the file already exists on
    disk (see services/documents_service.py). Returns the resolved settings
    actually used (not just None-if-not-overridden), so the caller can see
    what ran without having to know this project's own defaults.
    """
    resolved_vector_db = vector_db or read_setting(None, "RAG_VECTOR_DB", "chromadb")
    resolved_embedding_model = embedding_model or read_setting(
        None, "OPENAI_EMBED_MODEL", OpenAIEmbeddingClient.DEFAULT_MODEL
    )
    resolved_chunk_size = chunk_size or DEFAULT_CHUNK_SIZE
    resolved_chunk_overlap = chunk_overlap if chunk_overlap is not None else DEFAULT_CHUNK_OVERLAP

    logger.info(
        "Indexing document %s from %s (vector_db=%s, embedding_model=%s, chunk_size=%s, chunk_overlap=%s)",
        document_id,
        file_path,
        resolved_vector_db,
        resolved_embedding_model,
        resolved_chunk_size,
        resolved_chunk_overlap,
    )

    chunks = chunk_document(file_path, chunk_size=resolved_chunk_size, chunk_overlap=resolved_chunk_overlap)
    embeddings = embed_chunks(chunks, embedding_model=resolved_embedding_model)
    result = await index_chunks(document_id, chunks, embeddings, vector_db=resolved_vector_db)

    logger.info(
        "Document %s: %s (%d chunks indexed, %d stale chunks removed)",
        document_id,
        result["action"],
        result["chunks_indexed"],
        result["chunks_removed"],
    )

    return {
        "document_id": document_id,
        "vector_db": resolved_vector_db,
        "embedding_model": resolved_embedding_model,
        "chunk_size": resolved_chunk_size,
        "chunk_overlap": resolved_chunk_overlap,
        **result,
    }
