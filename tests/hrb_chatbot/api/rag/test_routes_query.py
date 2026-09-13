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


async def _fake_answer_query(
    query, top_k=5, vector_db=None, search_strategy=None, model_name=None, temperature=0.0, max_tokens=None
):
    return {
        "query": query,
        "answer": "This is a fake grounded answer.",
        "model_used": model_name or "gpt-4.1-mini",
        "sources": [
            {
                "document_id": "doc-1",
                "filename": "JPMC Healthcare Benefits.pdf",
                "chunk_index": 0,
                "text": "Some grounded chunk text.",
                "score": 0.95,
            }
        ],
        "vector_db": vector_db or "chromadb",
        "search_strategy": search_strategy or "similarity",
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


def test_dedicated_mmr_endpoint_always_uses_mmr_even_if_body_says_otherwise(monkeypatch):
    monkeypatch.setattr(routes_query.rag_service, "answer_query", _fake_answer_query)

    response = client.post(
        "/v1/rag-retrieval/query/mmr", json={"query": "test", "search_strategy": "similarity"}
    )

    assert response.status_code == 200
    assert response.json()["search_strategy"] == "mmr"


def test_unexpected_pipeline_failure_returns_a_clean_500(monkeypatch):
    async def _raise(*args, **kwargs):
        raise RuntimeError("vector store unreachable")

    monkeypatch.setattr(routes_query.rag_service, "answer_query", _raise)

    response = client.post("/v1/rag-retrieval/query", json={"query": "test"})

    assert response.status_code == 500
    assert "error" in response.json()
