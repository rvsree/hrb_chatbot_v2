"""Orchestrates answering one question against the indexed knowledge base.
No query decomposition yet - see ai/pre_processing/query_decompose.py
(Phase 5.1, not built) for where that will plug in."""

from src.hrb_chatbot.ai.rag_pipeline.query_retrieval.retriever import retrieve_chunks
from src.hrb_chatbot.ai.rag_pipeline.response_generation.response_generator import generate_answer
from src.hrb_chatbot.common.config.settings import get_active_llm_provider, get_active_vector_db
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rag_query_params import RagQueryParams

logger = get_logger("rag_pipeline.pipeline")


async def answer_query(params: RagQueryParams) -> dict:
    """Run the full pipeline: retrieve, generate. Exceptions aren't caught
    here - the router turns them into a clear error response."""
    resolved_vector_db = get_active_vector_db(params.vector_db)
    resolved_search_strategy = params.search_strategy or "similarity"
    resolved_llm_provider = get_active_llm_provider(params.llm_provider)

    logger.info(
        "Answering query %r (top_k=%s, vector_db=%s, search_strategy=%s, use_multi_query=%s, "
        "use_self_query=%s, llm_provider=%s)",
        params.query,
        params.top_k,
        resolved_vector_db,
        resolved_search_strategy,
        params.use_multi_query,
        params.use_self_query,
        resolved_llm_provider,
    )

    chunks, applied_filter = await retrieve_chunks(
        params.query,
        top_k=params.top_k,
        vector_db=resolved_vector_db,
        search_strategy=resolved_search_strategy,
        use_multi_query=params.use_multi_query,
        use_self_query=params.use_self_query,
        llm_provider=resolved_llm_provider,
    )
    generation = generate_answer(
        params.query, chunks, model_name=params.model_name, temperature=params.temperature,
        max_tokens=params.max_tokens,
    )

    logger.info("Query %r answered using %d chunk(s)", params.query, len(chunks))

    return {
        "query": params.query,
        "answer": generation["answer"],
        "model_used": generation["model_used"],
        "sources": chunks,
        "vector_db": resolved_vector_db,
        "search_strategy": resolved_search_strategy,
        "applied_filter": applied_filter,
    }
