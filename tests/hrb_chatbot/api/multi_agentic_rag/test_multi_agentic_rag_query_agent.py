"""Tests for POST /v1/multi-agentic-rag/query (Phase 61 scaffold) - the
pipeline is genuinely stubbed, so a well-formed request returns 501,
matching Phase 3/5's own precedent. Contract/gateway behavior only."""

from fastapi.testclient import TestClient

from src.hrb_chatbot.main import app

client = TestClient(app)

EMPLOYEE_USER_PROFILE = {"employee_id": "EMP052", "full_name": "Eddy Employee", "role": "employee"}


def _body(query: str = "What's my PTO balance and the parental leave policy?", user_profile=None) -> dict:
    return {"user_profile": EMPLOYEE_USER_PROFILE if user_profile is None else user_profile, "query": query}


def test_well_formed_query_returns_501_naming_the_stub_module():
    response = client.post("/v1/multi-agentic-rag/query", json=_body())

    assert response.status_code == 501
    body = response.json()
    assert body["code"] == "NOT_IMPLEMENTED"
    assert "orchestrator_router.py" in body["error"]


def test_missing_user_profile_is_401():
    response = client.post("/v1/multi-agentic-rag/query", json={"query": "test"})

    assert response.status_code == 401


def test_empty_query_is_422():
    response = client.post("/v1/multi-agentic-rag/query", json=_body(query=""))

    assert response.status_code == 422


def test_unknown_role_is_401():
    response = client.post(
        "/v1/multi-agentic-rag/query",
        json=_body(user_profile={"employee_id": "EMP052", "full_name": "Eddy Employee", "role": "made-up-role"}),
    )

    assert response.status_code == 401
