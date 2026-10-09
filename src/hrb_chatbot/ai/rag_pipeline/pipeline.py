"""Orchestrates answering one question against the indexed knowledge base."""

import asyncio
import time

from src.hrb_chatbot.ai.pre_processing import conversation_memory
from src.hrb_chatbot.ai.pre_processing.guardrails_input import check_input
from src.hrb_chatbot.ai.rag_core.guarded_pipeline import run_guarded_pipeline
from src.hrb_chatbot.ai.rag_core.tool_classification import classify_tool
from src.hrb_chatbot.ai.rag_pipeline.evaluations.golden_dataset_harness import evaluate_completeness, evaluate_groundedness
from src.hrb_chatbot.ai.rag_pipeline.query_retrieval.retriever import retrieve_chunks
from src.hrb_chatbot.ai.rag_pipeline.response_generation.response_generator import generate_answer
from src.hrb_chatbot.ai.rag_pipeline.tools.mcp_tools import try_route_to_mcp
from src.hrb_chatbot.common.clients.cache_client.answer_cache import build_cache_key
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.config.settings import get_active_llm_provider, get_active_vector_db, read_setting
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rag_query_params import RagQueryParams

logger = get_logger("rag_pipeline.pipeline")


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 1)


async def _score_live_answer(query: str, answer: str, sources: list[dict]) -> tuple[dict | None, float | None]:
    """Phase 109: live eval-judge scoring for one just-generated answer -
    skipped when there's no retrieved context to check groundedness
    against. Both judge calls are synchronous (evaluate_groundedness/
    evaluate_completeness make a real blocking HTTP call) - run via
    asyncio.to_thread() so one slow judge call can't stall the whole
    event loop, and in parallel via gather() so the two don't add up."""
    if not sources:
        return None, None

    eval_started_at = time.perf_counter()
    context_texts = [chunk["text"] for chunk in sources]
    groundedness, completeness = await asyncio.gather(
        asyncio.to_thread(evaluate_groundedness, answer, context_texts),
        asyncio.to_thread(evaluate_completeness, query, answer),
    )
    eval_scores = {
        "groundedness": groundedness["score"],
        "groundedness_verdict": groundedness["verdict"],
        "completeness": completeness["score"],
        "completeness_verdict": completeness["verdict"],
    }
    return eval_scores, _elapsed_ms(eval_started_at)


async def answer_query(params: RagQueryParams) -> dict:
    """Run the full pipeline: MCP fast-path (own routing, not a shared-core
    concern), else guardrail/retrieve/generate/guardrail/save via the
    Phase 98 shared core - GuardrailBlockedError becomes a 422 upstream."""
    started_at = time.perf_counter()
    # The MCP fast-path needs the checked query before deciding whether to
    # short-circuit at all - checked once here, then handed to the shared
    # core below as pre_checked_query so it isn't checked a second time.
    checked_query = await check_input(params.query)

    # Resolved up front so only the MCP path (which never calls the shared
    # core) can echo it - the normal RAG path below gets its own
    # resolution from run_guarded_pipeline().
    resolved_conversation_id = None
    if params.enable_conversation_memory:
        resolved_conversation_id = params.conversation_id or conversation_memory.new_conversation_id()

    mcp_result = await try_route_to_mcp(checked_query, params.employee_id)
    if mcp_result is not None:
        mcp_result["conversation_id"] = resolved_conversation_id
        mcp_result["served_from_cache"] = False
        mcp_result["llm_call_count"] = 0
        mcp_result["token_usage"] = None
        mcp_result["latency_ms"] = {
            "total": _elapsed_ms(started_at), "retrieval": None, "generation": None, "eval": None
        }
        mcp_result["eval_scores"] = None
        # Phase 126 - one-entry tools_used, same shape single/multi-agentic-rag already use.
        mcp_result["tools_used"] = [
            {
                "tool_name": mcp_result["routed_to"],
                "tool_input": checked_query,
                "tool_type": classify_tool(mcp_result["routed_to"]),
                "latency_ms": mcp_result.get("tool_latency_ms"),
                "success": True,  # try_route_to_mcp() already returned None on failure, falling through to RAG instead
            }
        ]
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

    # Phase 78/101/105: answer cache, exact match only, checked on every
    # turn - not just the first message of a fresh conversation. User
    # confirmed this tradeoff explicitly: a cache hit on a repeated
    # question mid-conversation (or asked by a different employee entirely
    # - the key never includes employee_id, see build_cache_key()) serves
    # the earlier answer verbatim, ignoring whatever conversation context
    # has accumulated since. Faster/cheaper, at the cost of a cached answer
    # occasionally not reflecting a mid-conversation follow-up's context.
    cache_key = build_cache_key(
        checked_query,
        top_k=resolved_top_k,
        vector_db=resolved_vector_db,
        search_strategy=resolved_search_strategy,
        model_name=params.model_name,
        temperature=resolved_temperature,
        max_tokens=params.max_tokens,
        use_multi_query=params.use_multi_query,
        use_self_query=params.use_self_query,
        llm_provider=resolved_llm_provider,
    )
    cached_result = await get_db_gateway().answer_cache().get(cache_key)
    if cached_result is not None:
        logger.info("Answer cache hit for %r", checked_query)
        # Never reuse the cached result's own conversation_id - it could be
        # a different caller's conversation entirely. This caller gets its
        # own (possibly freshly-generated) id, and the turn is saved under
        # it, so a follow-up still has this in its history.
        result = dict(cached_result)
        result["conversation_id"] = resolved_conversation_id
        if resolved_conversation_id:
            await conversation_memory.save_turn(
                resolved_conversation_id, params.employee_id, checked_query, result["answer"]
            )
            # Phase 112: this conversation's history now depends on this
            # cache entry - deleting the conversation can purge it later.
            await get_db_gateway().answer_cache().tag_conversation(resolved_conversation_id, cache_key)
        # Phase 107/109: this call made zero LLM/retrieval/eval-judge
        # calls - overwrite whatever latency_ms/token_usage the cached
        # dict carried from when it was FIRST generated, since those
        # describe that earlier call, not this one. eval_scores is the
        # one exception - left as-is below, reused rather than
        # recomputed, since it's a property of the (question, context,
        # answer) triple, which is identical for an exact cache hit.
        result["served_from_cache"] = True
        result["llm_call_count"] = 0
        result["token_usage"] = None
        result["latency_ms"] = {"total": _elapsed_ms(started_at), "retrieval": None, "generation": None, "eval": None}
        return result

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

    async def generate(generate_query: str, chat_history: list) -> dict:
        retrieval_started_at = time.perf_counter()
        chunks, applied_filter = await retrieve_chunks(
            generate_query,
            top_k=resolved_top_k,
            vector_db=resolved_vector_db,
            search_strategy=resolved_search_strategy,
            use_multi_query=params.use_multi_query,
            use_self_query=params.use_self_query,
            llm_provider=resolved_llm_provider,
        )
        retrieval_ms = _elapsed_ms(retrieval_started_at)

        generation_started_at = time.perf_counter()
        generation = generate_answer(
            generate_query, chunks, model_name=params.model_name, temperature=resolved_temperature,
            max_tokens=params.max_tokens, chat_history=chat_history,
        )
        generation_ms = _elapsed_ms(generation_started_at)

        logger.info("Query %r answered using %d chunk(s)", generate_query, len(chunks))
        return {
            "query": generate_query,
            "answer": generation["answer"],
            "model_used": generation["model_used"],
            "sources": chunks,
            "vector_db": resolved_vector_db,
            "search_strategy": resolved_search_strategy,
            "applied_filter": applied_filter,
            "served_from_cache": False,
            "llm_call_count": 1,
            "token_usage": generation.get("token_usage"),
            "latency_ms": {"total": None, "retrieval": retrieval_ms, "generation": generation_ms},
        }

    result = await run_guarded_pipeline(
        checked_query,
        params.employee_id,
        params.enable_conversation_memory,
        params.conversation_id,
        generate,
        pre_checked_query=checked_query,
    )
    result["eval_scores"], result["latency_ms"]["eval"] = await _score_live_answer(
        checked_query, result["answer"], result["sources"]
    )

    # total_ms covers the whole call (guardrails, cache check, retrieval,
    # generation, eval scoring, conversation-memory save) -
    # retrieval_ms/generation_ms/eval_ms above are the sub-steps timed
    # individually.
    result["latency_ms"]["total"] = _elapsed_ms(started_at)

    await get_db_gateway().answer_cache().set(cache_key, checked_query, result)
    if result.get("conversation_id"):
        await get_db_gateway().answer_cache().tag_conversation(result["conversation_id"], cache_key)

    return result
