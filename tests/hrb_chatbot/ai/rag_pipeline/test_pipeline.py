"""Tests for answer_query()'s default-resolution logic (ai/rag_pipeline/
pipeline.py) - top_k/temperature/search_strategy fall back to .env
(RAG_DEFAULT_TOP_K/RAG_DEFAULT_TEMPERATURE/RAG_DEFAULT_SEARCH_STRATEGY) when
the request omits them, not a hardcoded literal (Phase 38). retrieve_chunks/
generate_answer are faked - no real network call, this only tests the
resolution branching."""

from src.hrb_chatbot.ai.rag_pipeline import pipeline
from src.hrb_chatbot.common.rag_query_params import RagQueryParams


def _fake_retrieve_chunks_capturing(captured, chunks=None):
    async def _fake(query, top_k=5, vector_db=None, search_strategy=None, **kwargs):
        captured["top_k"] = top_k
        captured["search_strategy"] = search_strategy
        return (chunks or [], None)

    return _fake


def _fake_generate_answer_capturing(captured):
    def _fake(query, chunks, model_name=None, temperature=0.0, max_tokens=None, chat_history=None):
        captured["temperature"] = temperature
        return {"answer": "fake answer", "model_used": "gpt-4.1-mini"}

    return _fake


# Guardrails pass the query/answer through unchanged - these tests are about
# top_k/temperature resolution, not guardrail behavior (see test_pipeline_guardrails.py).
async def _fake_check_input(query):
    return query


async def _fake_check_output(query, answer):
    return answer


def _patch_guardrails(monkeypatch):
    monkeypatch.setattr(pipeline, "check_input", _fake_check_input)
    monkeypatch.setattr(pipeline, "check_output", _fake_check_output)


async def test_omitted_top_k_and_search_strategy_use_env_defaults(monkeypatch):
    captured = {}
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="How much leave?"))

    assert captured["top_k"] == 5  # RAG_DEFAULT_TOP_K in .env
    assert captured["search_strategy"] == "similarity"  # RAG_DEFAULT_SEARCH_STRATEGY in .env


async def test_explicit_top_k_and_search_strategy_are_not_overridden(monkeypatch):
    captured = {}
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test", top_k=3, search_strategy="mmr"))

    assert captured["top_k"] == 3
    assert captured["search_strategy"] == "mmr"


async def test_omitted_temperature_uses_env_default(monkeypatch):
    captured = {}
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test"))

    assert captured["temperature"] == 0.0  # RAG_DEFAULT_TEMPERATURE in .env


async def test_explicit_temperature_zero_is_not_treated_as_omitted(monkeypatch):
    """The real edge case this resolution has to get right: `params.temperature
    or default` would wrongly replace an explicit 0.0 (falsy) with the .env
    default - the code must check `is None`, not truthiness."""
    captured = {}
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test", temperature=0.0))

    assert captured["temperature"] == 0.0


async def test_explicit_nonzero_temperature_passes_through(monkeypatch):
    captured = {}
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test", temperature=0.7))

    assert captured["temperature"] == 0.7


# Phase 49: a matched query short-circuits before retrieve_chunks/generate_answer
# are ever called - the two spies below prove retrieval/generation were skipped.
async def test_mcp_routable_query_skips_retrieval_and_generation(monkeypatch):
    called = {"retrieve": False, "generate": False}

    async def _spy_retrieve_chunks(*args, **kwargs):
        called["retrieve"] = True
        return [], None

    def _spy_generate_answer(*args, **kwargs):
        called["generate"] = True
        return {"answer": "should not be used", "model_used": "gpt-4.1-mini"}

    async def _fake_try_route_to_mcp(query, employee_id):
        return {"query": query, "answer": "MCP answer", "model_used": None, "sources": [],
                "vector_db": None, "search_strategy": None, "applied_filter": None, "routed_to": "get_leave_balance"}

    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _spy_retrieve_chunks)
    monkeypatch.setattr(pipeline, "generate_answer", _spy_generate_answer)
    monkeypatch.setattr(pipeline, "try_route_to_mcp", _fake_try_route_to_mcp)

    result = await pipeline.answer_query(RagQueryParams(query="What's my PTO balance?", employee_id="EMP052"))

    assert result["answer"] == "MCP answer"
    assert called["retrieve"] is False
    assert called["generate"] is False


# Phase 58: server-side conversation memory - disabled by default, opt-in
# via RagQueryParams.enable_conversation_memory.
async def test_conversation_memory_disabled_by_default_no_conversation_id(monkeypatch):
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing({}))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing({}))

    result = await pipeline.answer_query(RagQueryParams(query="test"))

    assert result["conversation_id"] is None


async def test_enabling_conversation_memory_generates_and_saves_a_turn(monkeypatch):
    from src.hrb_chatbot.ai.pre_processing import conversation_memory

    conversation_memory._CONVERSATIONS.clear()
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing({}, chunks=[{"filename": "x", "chunk_index": 0, "text": "y"}]))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing({}))

    result = await pipeline.answer_query(RagQueryParams(query="test question", enable_conversation_memory=True))

    assert result["conversation_id"] is not None
    saved = conversation_memory.load_history(result["conversation_id"])
    assert [m.content for m in saved] == ["test question", "fake answer"]


async def test_mcp_routed_answer_echoes_conversation_id_but_does_not_save_a_turn(monkeypatch):
    from src.hrb_chatbot.ai.pre_processing import conversation_memory

    conversation_memory._CONVERSATIONS.clear()

    async def _fake_try_route_to_mcp(query, employee_id):
        return {"query": query, "answer": "MCP answer", "model_used": "mcp:x", "sources": [],
                "vector_db": "n/a (mcp)", "search_strategy": "n/a (mcp)", "applied_filter": None}

    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(pipeline, "try_route_to_mcp", _fake_try_route_to_mcp)

    result = await pipeline.answer_query(
        RagQueryParams(query="What's my PTO balance?", employee_id="EMP052", enable_conversation_memory=True)
    )

    assert result["conversation_id"] is not None
    assert conversation_memory.load_history(result["conversation_id"]) == []


async def test_an_existing_conversation_id_is_passed_to_generate_answer_as_chat_history(monkeypatch):
    from src.hrb_chatbot.ai.pre_processing import conversation_memory

    conversation_memory._CONVERSATIONS.clear()
    conversation_memory.save_turn("conv-1", "earlier question", "earlier answer")
    captured = {}
    _patch_guardrails(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "retrieve_chunks",
        _fake_retrieve_chunks_capturing(captured, chunks=[{"filename": "x", "chunk_index": 0, "text": "y"}]),
    )

    def _fake_generate_answer(query, chunks, model_name=None, temperature=0.0, max_tokens=None, chat_history=None):
        captured["chat_history"] = chat_history
        return {"answer": "fake answer", "model_used": "gpt-4.1-mini"}

    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer)

    await pipeline.answer_query(
        RagQueryParams(query="follow-up question", enable_conversation_memory=True, conversation_id="conv-1")
    )

    assert [m.content for m in captured["chat_history"]] == ["earlier question", "earlier answer"]
