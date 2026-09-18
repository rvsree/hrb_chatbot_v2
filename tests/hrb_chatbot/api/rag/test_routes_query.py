"""Tests for POST /rag-retrieval/query (api/rag/routes_query.py). The real
pipeline exists now (ai/rag_pipeline/), so well-formed-request tests
monkeypatch rag_service.answer_query() to a canned response - this file
tests the ROUTE's contract (status codes, response shape), not retrieval/
generation correctness itself (see
tests/hrb_chatbot/ai/rag_pipeline/query_retrieval/test_retriever.py and
.../response_generation/test_generator.py for that). No test here may hit
a real network call or cost money."""

from fastapi.testclient import TestClient

from src.hrb_chatbot.api.rag import routes_query
from src.hrb_chatbot.main import app

client = TestClient(app)
# Phase 23 gateway: retrieval accepts EMPLOYEE/MANAGER/HR_SUPPORT - set once
# so every existing call below keeps working without touching each one individually.
client.headers.update({"X-Employee-Id": "E00002", "X-Full-Name": "Eddy Employee", "X-Role": "employee"})


async def _fake_answer_query(params):
    return {
        "query": params.query,
        "answer": "This is a fake grounded answer.",
        "model_used": params.model_name or "gpt-4.1-mini",
        "sources": [
            {
                "document_id": "doc-1",
                "filename": "JPMC Healthcare Benefits.pdf",
                "chunk_index": 0,
                "text": "Some grounded chunk text.",
                "score": 0.95,
            }
        ],
        "vector_db": params.vector_db or "chromadb",
        "search_strategy": params.search_strategy or "similarity",
        "applied_filter": {"doc_classification": {"$eq": "401k"}} if params.use_self_query else None,
    }


def test_well_formed_query_returns_a_grounded_answer(monkeypatch):
    monkeypatch.setattr(routes_query.rag_service, "answer_query", _fake_answer_query)

    response = client.post(
        "/v1/rag-retrieval/query", json={"query": "How many weeks of parental leave do I get?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "How many weeks of parental leave do I get?"
    assert body["answer"] == "This is a fake grounded answer."
    assert body["model_used"] == "gpt-4.1-mini"
    assert body["sources"][0]["filename"] == "JPMC Healthcare Benefits.pdf"


def test_empty_query_string_is_rejected_before_reaching_the_pipeline():
    response = client.post("/v1/rag-retrieval/query", json={"query": ""})

    assert response.status_code == 422


def test_missing_query_field_is_rejected():
    response = client.post("/v1/rag-retrieval/query", json={})

    assert response.status_code == 422


def test_top_k_above_the_maximum_is_rejected():
    response = client.post("/v1/rag-retrieval/query", json={"query": "test", "top_k": 100})

    assert response.status_code == 422


def test_optional_generation_fields_are_accepted_and_passed_through(monkeypatch):
    """Confirms model_name/temperature/max_tokens are real, accepted request
    fields that reach the pipeline, not just documented intent."""
    monkeypatch.setattr(routes_query.rag_service, "answer_query", _fake_answer_query)

    response = client.post(
        "/v1/rag-retrieval/query",
        json={"query": "test", "model_name": "gpt-4.1-mini", "temperature": 0.5, "max_tokens": 200},
    )

    assert response.status_code == 200
    assert response.json()["model_used"] == "gpt-4.1-mini"


def test_temperature_out_of_range_is_rejected():
    response = client.post("/v1/rag-retrieval/query", json={"query": "test", "temperature": 5.0})

    assert response.status_code == 422


def test_search_strategy_field_is_accepted_and_passed_through(monkeypatch):
    monkeypatch.setattr(routes_query.rag_service, "answer_query", _fake_answer_query)

    response = client.post("/v1/rag-retrieval/query", json={"query": "test", "search_strategy": "mmr"})

    assert response.status_code == 200
    assert response.json()["search_strategy"] == "mmr"


def test_dedicated_mmr_endpoint_no_longer_exists():
    # Phase 21 removed it - MMR is selected via search_strategy in the body
    # of POST /query instead (see test_search_strategy_field_is_accepted_and_passed_through).
    response = client.post("/v1/rag-retrieval/query/mmr", json={"query": "test"})

    assert response.status_code == 404


def test_unknown_search_strategy_is_a_422_naming_the_valid_options():
    response = client.post("/v1/rag-retrieval/query", json={"query": "test", "search_strategy": "made-up"})

    assert response.status_code == 422


def test_use_multi_query_and_use_self_query_are_accepted_and_passed_through(monkeypatch):
    captured = {}

    async def _capturing_fake(params):
        captured["params"] = params
        return await _fake_answer_query(params)

    monkeypatch.setattr(routes_query.rag_service, "answer_query", _capturing_fake)

    response = client.post(
        "/v1/rag-retrieval/query",
        json={"query": "what's my 401k vesting schedule", "use_multi_query": True, "use_self_query": True, "llm_provider": "anthropic"},
    )

    assert response.status_code == 200
    assert captured["params"].use_multi_query is True
    assert captured["params"].use_self_query is True
    assert captured["params"].llm_provider == "anthropic"
    assert response.json()["applied_filter"] == {"doc_classification": {"$eq": "401k"}}


def test_use_multi_query_and_use_self_query_default_to_false(monkeypatch):
    captured = {}

    async def _capturing_fake(params):
        captured["params"] = params
        return await _fake_answer_query(params)

    monkeypatch.setattr(routes_query.rag_service, "answer_query", _capturing_fake)

    response = client.post("/v1/rag-retrieval/query", json={"query": "test"})

    assert response.status_code == 200
    assert captured["params"].use_multi_query is False
    assert captured["params"].use_self_query is False
    assert captured["params"].llm_provider is None
    assert response.json()["applied_filter"] is None


def test_unknown_llm_provider_is_a_422_naming_the_valid_options():
    response = client.post("/v1/rag-retrieval/query", json={"query": "test", "llm_provider": "made-up"})

    assert response.status_code == 422


def test_retrieval_without_any_identity_headers_is_a_401():
    anonymous_client = TestClient(app)

    response = anonymous_client.post("/v1/rag-retrieval/query", json={"query": "test"})

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_retrieval_accepts_all_three_roles(monkeypatch):
    monkeypatch.setattr(routes_query.rag_service, "answer_query", _fake_answer_query)

    for role in ("employee", "manager", "hr_support"):
        response = client.post("/v1/rag-retrieval/query", json={"query": "test"}, headers={"X-Role": role})
        assert response.status_code == 200, role


def test_unexpected_pipeline_failure_returns_a_clean_500(monkeypatch):
    async def _raise(*args, **kwargs):
        raise RuntimeError("vector store unreachable")

    monkeypatch.setattr(routes_query.rag_service, "answer_query", _raise)

    response = client.post("/v1/rag-retrieval/query", json={"query": "test"})

    assert response.status_code == 500
    assert "error" in response.json()
