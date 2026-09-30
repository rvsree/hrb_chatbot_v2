"""Orchestrates answering one question against the indexed knowledge base."""

from src.hrb_chatbot.ai.pre_processing import conversation_memory
from src.hrb_chatbot.ai.pre_processing.guardrails_input import check_input
from src.hrb_chatbot.ai.rag_pipeline.query_retrieval.retriever import retrieve_chunks
from src.hrb_chatbot.ai.rag_pipeline.response_generation.guardrails_output import check_output
from src.hrb_chatbot.ai.rag_pipeline.response_generation.response_generator import generate_answer
from src.hrb_chatbot.ai.rag_pipeline.tools.mcp_tools import try_route_to_mcp
from src.hrb_chatbot.common.config.settings import get_active_llm_provider, get_active_vector_db, read_setting
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rag_query_params import RagQueryParams

logger = get_logger("rag_pipeline.pipeline")


async def answer_query(params: RagQueryParams) -> dict:
    """Run the full pipeline: guardrail, retrieve, generate, guardrail - GuardrailBlockedError becomes a 422 upstream."""
    checked_query = await check_input(params.query)

    # Resolved up front so every response path (including MCP) can echo it, but only the normal RAG path saves history.
    resolved_conversation_id = None
    if params.enable_conversation_memory:
        resolved_conversation_id = params.conversation_id or conversation_memory.new_conversation_id()

    mcp_result = await try_route_to_mcp(checked_query, params.employee_id)
    if mcp_result is not None:
        mcp_result["conversation_id"] = resolved_conversation_id
        return mcp_result

    resolved_vector_db = get_active_vector_db(params.vector_db)
    resolved_search_strategy = params.search_strategy or read_setting(
        None, "RAG_DEFAULT_SEARCH_STRATEGY", "similarity"
    )
    resolved_llm_provider = get_active_llm_provider(params.llm_provider)
    resolved_top_k = params.top_k or int(read_setting(None, "RAG_DEFAULT_TOP_K", 5))
    if params.temperature is None:
        resolved_temperature = float(read_setting(None, "RAG_DEFAULT_TEMPERATURE", 0.0))
    else:
        resolved_temperature = params.temperature

    logger.info(
        "Answering query %r (top_k=%s, vector_db=%s, search_strategy=%s, use_multi_query=%s, "
        "use_self_query=%s, llm_provider=%s)",
        checked_query,
        resolved_top_k,
        resolved_vector_db,
        resolved_search_strategy,
        params.use_multi_query,
        params.use_self_query,
        resolved_llm_provider,
    )

    chunks, applied_filter = await retrieve_chunks(
        checked_query,
        top_k=resolved_top_k,
        vector_db=resolved_vector_db,
        search_strategy=resolved_search_strategy,
        use_multi_query=params.use_multi_query,
        use_self_query=params.use_self_query,
        llm_provider=resolved_llm_provider,
    )
    chat_history = conversation_memory.load_history(resolved_conversation_id) if resolved_conversation_id else None
    generation = generate_answer(
        checked_query, chunks, model_name=params.model_name, temperature=resolved_temperature,
        max_tokens=params.max_tokens, chat_history=chat_history,
    )
    checked_answer = await check_output(checked_query, generation["answer"])

    if resolved_conversation_id:
        conversation_memory.save_turn(resolved_conversation_id, checked_query, checked_answer)

    logger.info("Query %r answered using %d chunk(s)", checked_query, len(chunks))

    return {
        "query": checked_query,
        "answer": checked_answer,
        "model_used": generation["model_used"],
        "sources": chunks,
        "vector_db": resolved_vector_db,
        "search_strategy": resolved_search_strategy,
        "applied_filter": applied_filter,
        "conversation_id": resolved_conversation_id,
    }
