"""Tests for GET /ping and /health (api/admin/routes_health.py) - provider
params default, override, and reject a bad value via FastAPI's own
Query()-bound validation (api/dependencies.py)."""

from fastapi.testclient import TestClient

from src.hrb_chatbot.api.admin import routes_health
from src.hrb_chatbot.main import app

client = TestClient(app)


def test_ping_is_free_and_instant():
    response = client.get("/hrb-chatbot/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_defaults_provider_params_when_omitted(monkeypatch):
    captured = {}

    def _fake_check_all(provider, metadata_provider, vector_provider):
        captured.update(provider=provider, metadata_provider=metadata_provider, vector_provider=vector_provider)
        return {"status": "healthy"}

    monkeypatch.setattr(routes_health.agent_health, "check_all_backend_services", _fake_check_all)

    response = client.get("/hrb-chatbot/health")

    assert response.status_code == 200
    assert captured["provider"] == "openai"
    assert captured["metadata_provider"] == "sqlite"
    assert captured["vector_provider"] == "chromadb"


def test_health_query_params_override_the_defaults(monkeypatch):
    captured = {}

    def _fake_check_all(provider, metadata_provider, vector_provider):
        captured.update(provider=provider, metadata_provider=metadata_provider, vector_provider=vector_provider)
        return {"status": "healthy"}

    monkeypatch.setattr(routes_health.agent_health, "check_all_backend_services", _fake_check_all)

    response = client.get("/hrb-chatbot/health?provider=anthropic&metadata_provider=postgres&vector_provider=pinecone")

    assert response.status_code == 200
    assert captured["provider"] == "anthropic"
    assert captured["metadata_provider"] == "postgres"
    assert captured["vector_provider"] == "pinecone"


def test_health_rejects_an_unknown_provider_value_with_422():
    response = client.get("/hrb-chatbot/health?provider=not-a-real-provider")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "not-a-real-provider" in str(body["details"])
