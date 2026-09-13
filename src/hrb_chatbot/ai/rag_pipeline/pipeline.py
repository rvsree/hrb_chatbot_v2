"""Orchestrates answering one question against the indexed knowledge base.

MVP implementation, 2026-09-10: retrieve_chunks() and generate_answer() call
the real pipeline now (ai/rag_pipeline/query_retrieval/,
ai/rag_pipeline/response_generation/). decompose_query() is deliberately
still a trivial passthrough, not real decomposition - see its own docstring
for why that's not the same as implementing Phase 5.1.
"""

from src.hrb_chatbot.ai.rag_pipeline.query_retrieval.retriever import retrieve_chunks as _retrieve_chunks
from src.hrb_chatbot.ai.rag_pipeline.response_generation.generator import generate_answer as _generate_answer
from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_pipeline.pipeline")


def decompose_query(query: str) -> list[str]:
    """Break a complex question into simpler sub-questions to retrieve for.

    MVP: always returns [query] unchanged - this is NOT Phase 5.1 (that's
    real LLM-based decomposition, hand-written, in
    ai/pre_processing/query_decompose.py, still empty and untouched here on
    purpose). This passthrough exists only so retrieve_chunks() below can
    already accept a list of sub-queries without its own signature changing
    once real decomposition lands.
    """
    return [query]


async def retrieve_chunks(
    queries: list[str], top_k: int = 5, vector_db: str | None = None, search_strategy: str | None = None
) -> list[dict]:
    """Embed each query and retrieve the top_k most relevant chunks overall.

    Each result dict has document_id, filename, chunk_index, text, score
    (models/rag.py's RetrievedChunk). See ai/rag_pipeline/query_retrieval/retriever.py.
    """
    return await _retrieve_chunks(queries, top_k=top_k, vector_db=vector_db, search_strategy=search_strategy)


def generate_answer(
    query: str,
    chunks: list[dict],
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict:
    """Generate a grounded answer to query, using only the given chunks as context.
    Returns {"answer": str, "model_used": str}. See
    ai/rag_pipeline/response_generation/generator.py.
    """
    return _generate_answer(
        query, chunks, model_name=model_name, temperature=temperature, max_tokens=max_tokens
    )


async def answer_query(
    query: str,
    top_k: int = 5,
    vector_db: str | None = None,
    search_strategy: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict:
    """Run the full pipeline for one question: decompose, retrieve, generate.

    Exceptions are deliberately not caught here - the router turns them into a clear error response.
    """
    resolved_vector_db = vector_db or read_setting(None, "RAG_VECTOR_DB", "chromadb")
    resolved_search_strategy = search_strategy or "similarity"

    logger.info(
        "Answering query %r (top_k=%s, vector_db=%s, search_strategy=%s)",
        query,
        top_k,
        resolved_vector_db,
        resolved_search_strategy,
    )

    sub_queries = decompose_query(query)
    chunks = await retrieve_chunks(
        sub_queries, top_k=top_k, vector_db=resolved_vector_db, search_strategy=resolved_search_strategy
    )
    generation = generate_answer(
        query, chunks, model_name=model_name, temperature=temperature, max_tokens=max_tokens
    )

    logger.info("Query %r answered using %d chunk(s)", query, len(chunks))

    return {
        "query": query,
        "answer": generation["answer"],
        "model_used": generation["model_used"],
        "sources": chunks,
        "vector_db": resolved_vector_db,
        "search_strategy": resolved_search_strategy,
    }
