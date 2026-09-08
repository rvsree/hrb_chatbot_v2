"""Tests for POST /rag/query - api/rag/routes_query.py.

The underlying pipeline (ai/rag_pipeline/pipeline.py) is a hand-written
stub today (Phase 6 isn't built yet - see docs/RAG-ROADMAP.md), so these
tests can only confirm today's *stub* behavior: a clear 501 naming the
module to implement, and that request validation works without needing
Phase 6 to exist at all. Once Phase 6 lands, add a new test file for the
real grounded-answer behavior rather than rewriting these - they're still
correct regression tests for "the stub fails the right way" even after
it's no longer a stub for the happy path.

Uses FastAPI's own TestClient (httpx underneath, already in
requirements.txt) - no running server needed, no network call.
"""

from fastapi.testclient import TestClient

from src.hrb_chatbot.main import app

client = TestClient(app)


def test_well_formed_query_returns_501_naming_the_module_to_implement():
    response = client.post("/v1/rag/query", json={"query": "How many weeks of parental leave do I get?"})

    assert response.status_code == 501
    body = response.json()
    assert "ai/rag_pipeline/pipeline.py" in body["error"] or "not implemented" in body["error"].lower()


def test_empty_query_string_is_rejected_before_reaching_the_stub():
    response = client.post("/v1/rag/query", json={"query": ""})

    assert response.status_code == 422


def test_missing_query_field_is_rejected():
    response = client.post("/v1/rag/query", json={})

    assert response.status_code == 422


def test_top_k_above_the_maximum_is_rejected():
    response = client.post("/v1/rag/query", json={"query": "test", "top_k": 100})

    assert response.status_code == 422


def test_optional_generation_fields_are_accepted_with_defaults():
    """Confirms the model_name/temperature/max_tokens fields added to the
    API contract are real, accepted request fields - not just documented
    intent - even though the pipeline behind them is still a stub."""
    response = client.post(
        "/v1/rag/query",
        json={"query": "test", "model_name": "gpt-4.1-mini", "temperature": 0.5, "max_tokens": 200},
    )

    # Still 501 (the stub), not 422 - proves these fields were accepted by
    # request validation and passed through, not rejected as unexpected.
    assert response.status_code == 501


def test_temperature_out_of_range_is_rejected():
    response = client.post("/v1/rag/query", json={"query": "test", "temperature": 5.0})

    assert response.status_code == 422
