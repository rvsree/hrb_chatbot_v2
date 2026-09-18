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
    def _fake(query, chunks, model_name=None, temperature=0.0, max_tokens=None):
        captured["temperature"] = temperature
        return {"answer": "fake answer", "model_used": "gpt-4.1-mini"}

    return _fake


async def test_omitted_top_k_and_search_strategy_use_env_defaults(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="How much leave?"))

    assert captured["top_k"] == 5  # RAG_DEFAULT_TOP_K in .env
    assert captured["search_strategy"] == "similarity"  # RAG_DEFAULT_SEARCH_STRATEGY in .env


async def test_explicit_top_k_and_search_strategy_are_not_overridden(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test", top_k=3, search_strategy="mmr"))

    assert captured["top_k"] == 3
    assert captured["search_strategy"] == "mmr"


async def test_omitted_temperature_uses_env_default(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test"))

    assert captured["temperature"] == 0.0  # RAG_DEFAULT_TEMPERATURE in .env


async def test_explicit_temperature_zero_is_not_treated_as_omitted(monkeypatch):
    """The real edge case this resolution has to get right: `params.temperature
    or default` would wrongly replace an explicit 0.0 (falsy) with the .env
    default - the code must check `is None`, not truthiness."""
    captured = {}
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test", temperature=0.0))

    assert captured["temperature"] == 0.0


async def test_explicit_nonzero_temperature_passes_through(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "retrieve_chunks", _fake_retrieve_chunks_capturing(captured))
    monkeypatch.setattr(pipeline, "generate_answer", _fake_generate_answer_capturing(captured))

    await pipeline.answer_query(RagQueryParams(query="test", temperature=0.7))

    assert captured["temperature"] == 0.7
