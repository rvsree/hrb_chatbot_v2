"""Orchestrates turning one stored PDF into indexed, searchable chunks."""

from src.hrb_chatbot.ai.doc_processing.chunking.text_chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_text,
    extract_text_from_pdf,
)
from src.hrb_chatbot.ai.doc_processing.embedding.embedding_generator import generate_embeddings
from src.hrb_chatbot.ai.doc_processing.indexing.vector_indexer import write_chunks
from src.hrb_chatbot.ai.doc_processing.metadata_extraction.document_metadata_extractor import (
    extract_document_metadata,
)
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.clients.llm_client.openai_client import OpenAIEmbeddingClient
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("doc_processing.pipeline")


def chunk_document(text: str, chunk_size: int | None = None, chunk_overlap: int | None = None) -> list[str]:
    """Split already-extracted text into overlapping chunks."""
    if chunk_overlap is None:
        resolved_overlap = DEFAULT_CHUNK_OVERLAP
    else:
        resolved_overlap = chunk_overlap

    return chunk_text(
        text,
        chunk_size=chunk_size or DEFAULT_CHUNK_SIZE,
        chunk_overlap=resolved_overlap,
    )


def embed_chunks(chunks: list[str], embedding_model: str | None = None) -> list[list[float]]:
    return generate_embeddings(chunks, embedding_model=embedding_model)


async def index_chunks(
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    vector_db: str | None = None,
    embedding_model: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict:
    return await write_chunks(
        document_id,
        chunks,
        embeddings,
        vector_db=vector_db,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


async def index_document(
    document_id: str,
    file_path: str,
    vector_db: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model: str | None = None,
) -> dict:
    resolved_vector_db = vector_db or read_setting(None, "RAG_VECTOR_DB", "chromadb")
    resolved_embedding_model = embedding_model or read_setting(
        None, "OPENAI_EMBED_MODEL", OpenAIEmbeddingClient.DEFAULT_MODEL
    )
    resolved_chunk_size = chunk_size or DEFAULT_CHUNK_SIZE

    if chunk_overlap is None:
        resolved_chunk_overlap = DEFAULT_CHUNK_OVERLAP
    else:
        resolved_chunk_overlap = chunk_overlap

    logger.info(
        "Indexing document %s from %s (vector_db=%s, embedding_model=%s, chunk_size=%s, chunk_overlap=%s)",
        document_id,
        file_path,
        resolved_vector_db,
        resolved_embedding_model,
        resolved_chunk_size,
        resolved_chunk_overlap,
    )

    text = extract_text_from_pdf(file_path)
    chunks = chunk_document(text, chunk_size=resolved_chunk_size, chunk_overlap=resolved_chunk_overlap)
    embeddings = embed_chunks(chunks, embedding_model=resolved_embedding_model)
    result = await index_chunks(
        document_id,
        chunks,
        embeddings,
        vector_db=resolved_vector_db,
        embedding_model=resolved_embedding_model,
        chunk_size=resolved_chunk_size,
        chunk_overlap=resolved_chunk_overlap,
    )

    logger.info(
        "Document %s: %s (%d chunks indexed, %d stale chunks removed)",
        document_id,
        result["action"],
        result["chunks_indexed"],
        result["chunks_removed"],
    )

    # Document-level metadata (owner/department/doc_type/purpose) doesn't
    # change between re-indexes of the same content, so it's only extracted
    # once, on the document's first successful index - not repeated (and
    # not re-billed) on every subsequent re-index. Best-effort: a failure
    # here is logged and swallowed, never allowed to fail the index itself.
    if result["action"] == "insert":
        try:
            extracted_metadata = extract_document_metadata(text)
            await get_db_gateway().metadata_store().record_document_metadata(document_id, **extracted_metadata)
        except Exception as error:
            logger.warning(
                "Document metadata extraction/recording failed for %s: %s: %s",
                document_id,
                type(error).__name__,
                error,
            )

    return {
        "document_id": document_id,
        "vector_db": resolved_vector_db,
        "embedding_model": resolved_embedding_model,
        "chunk_size": resolved_chunk_size,
        "chunk_overlap": resolved_chunk_overlap,
        **result,
    }
