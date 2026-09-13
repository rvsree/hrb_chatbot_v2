"""Tests for main.py's global exception handler and request-validation
bounds. Core claim: when something unexpected breaks, the client gets a
generic, safe message - never raw exception text, which could leak
internal details (file paths, connection strings, etc.)."""

from fastapi.testclient import TestClient

from src.hrb_chatbot.api.rag import routes_query
from src.hrb_chatbot.main import app
from src.hrb_chatbot.services import documents_service

client = TestClient(app)

SECRET_LOOKING_MESSAGE = "connection failed: password=supersecret123 at internal-db-host:5432"


def test_an_unexpected_exception_never_leaks_its_raw_message_to_the_client(monkeypatch):
    async def raise_with_sensitive_details():
        raise RuntimeError(SECRET_LOOKING_MESSAGE)

    monkeypatch.setattr(documents_service, "list_documents", raise_with_sensitive_details)

    # raise_server_exceptions=False: otherwise TestClient re-raises the
    # exception instead of returning the handler's real HTTP response.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/v1/rag-ingestion/documents")

    assert response.status_code == 500
    body_text = response.text
    assert SECRET_LOOKING_MESSAGE not in body_text
    assert "password" not in body_text
    assert "internal-db-host" not in body_text


def test_the_generic_error_response_still_has_the_project_s_standard_shape(monkeypatch):
    async def raise_unexpectedly():
        raise RuntimeError(SECRET_LOOKING_MESSAGE)

    monkeypatch.setattr(documents_service, "list_documents", raise_unexpectedly)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/v1/rag-ingestion/documents")

    # Still {"error": ...} (json_error()'s shape), not FastAPI's default
    # {"detail": ...} - the handler normalizes every error response.
    body = response.json()
    assert "error" in body
    assert body["code"] == "INTERNAL_ERROR"


def test_query_longer_than_the_max_length_is_rejected():
    too_long_query = "a" * 2001

    response = client.post("/v1/rag-retrieval/query", json={"query": too_long_query})

    assert response.status_code == 422
    # Pydantic's own validation errors used to bypass json_error() entirely
    # and return FastAPI's default {"detail": [...]} shape - the
    # RequestValidationError handler in main.py now normalizes this too.
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "error" in body
    assert "details" in body  # the raw Pydantic error list, for debugging


def test_query_at_exactly_the_max_length_is_accepted_by_validation(monkeypatch):
    async def _fake_answer_query(query, **kwargs):
        return {
            "query": query,
            "answer": "fake answer",
            "model_used": "gpt-4.1-mini",
            "sources": [],
            "vector_db": "chromadb",
        }

    monkeypatch.setattr(routes_query.rag_service, "answer_query", _fake_answer_query)
    exactly_max_length_query = "a" * 2000

    response = client.post("/v1/rag-retrieval/query", json={"query": exactly_max_length_query})

    # 200, not 422 - confirms validation accepted it and the request reached
    # the route handler (the pipeline itself is faked, not under test here).
    assert response.status_code == 200
