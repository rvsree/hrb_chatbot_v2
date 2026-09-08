"""Tests for the global exception handler in main.py, and the request-
validation bounds that reject obviously-wrong input before it ever
reaches a route handler.

The core claim under test: when something genuinely unexpected breaks,
the client gets a generic, safe message - never the raw exception text,
which could contain internal details (a file path, a connection string
fragment, anything from a caught exception's own __str__).
"""

from fastapi.testclient import TestClient

from src.hrb_chatbot.main import app
from src.hrb_chatbot.services import documents_service

client = TestClient(app)

SECRET_LOOKING_MESSAGE = "connection failed: password=supersecret123 at internal-db-host:5432"


def test_an_unexpected_exception_never_leaks_its_raw_message_to_the_client(monkeypatch):
    async def raise_with_sensitive_details():
        raise RuntimeError(SECRET_LOOKING_MESSAGE)

    monkeypatch.setattr(documents_service, "list_documents", raise_with_sensitive_details)

    # raise_server_exceptions=False: without this, TestClient re-raises the
    # exception into the test itself instead of letting main.py's own
    # exception handler produce a real HTTP response - we want to inspect
    # that response, not the exception.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/v1/rag/documents")

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
        response = test_client.get("/v1/rag/documents")

    # Still {"error": "..."} - json_error()'s own shape - not FastAPI's
    # default {"detail": "..."} shape, which the global handler deliberately
    # replaces so every error response in this project looks the same
    # regardless of which layer caught it.
    body = response.json()
    assert "error" in body


def test_query_longer_than_the_max_length_is_rejected():
    too_long_query = "a" * 2001

    response = client.post("/v1/rag/query", json={"query": too_long_query})

    assert response.status_code == 422


def test_query_at_exactly_the_max_length_is_accepted_by_validation():
    exactly_max_length_query = "a" * 2000

    response = client.post("/v1/rag/query", json={"query": exactly_max_length_query})

    # 501 (the stub), not 422 - confirms validation accepted it and the
    # request reached the route handler.
    assert response.status_code == 501
