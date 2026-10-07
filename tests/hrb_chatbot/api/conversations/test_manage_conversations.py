"""Tests for /v1/conversations (Phase 76 DELETE, Phase 116 GET list/detail) -
conversation_memory is faked, no real database."""

from fastapi.testclient import TestClient

from src.hrb_chatbot.api.conversations import manage_conversations
from src.hrb_chatbot.main import app
from tests.conftest import FakeDBGateway

client = TestClient(app)

EMPLOYEE_USER_PROFILE = {"employee_id": "EMP052", "full_name": "Eddy Employee", "role": "employee"}


def _body(user_profile=None) -> dict:
    return {"user_profile": EMPLOYEE_USER_PROFILE if user_profile is None else user_profile}


def _fake_answer_cache(monkeypatch):
    """Phase 112: delete_conversation() now calls get_db_gateway().answer_cache()
    too - fake it, or every DELETE test here makes a real Redis call."""
    monkeypatch.setattr(manage_conversations, "get_db_gateway", lambda: FakeDBGateway())


def test_well_formed_request_returns_turns_deleted(monkeypatch):
    _fake_answer_cache(monkeypatch)

    async def _fake_delete_conversation(conversation_id, employee_id):
        assert conversation_id == "conv-1"
        assert employee_id == "EMP052"
        return 4

    monkeypatch.setattr(manage_conversations.conversation_memory, "delete_conversation", _fake_delete_conversation)

    response = client.request("DELETE", "/v1/conversations/conv-1", json=_body())

    assert response.status_code == 200
    body = response.json()
    assert body == {"conversation_id": "conv-1", "turns_deleted": 4}


def test_someone_elses_conversation_returns_zero_deleted(monkeypatch):
    _fake_answer_cache(monkeypatch)

    async def _fake_delete_conversation(conversation_id, employee_id):
        return 0

    monkeypatch.setattr(manage_conversations.conversation_memory, "delete_conversation", _fake_delete_conversation)

    response = client.request("DELETE", "/v1/conversations/not-mine", json=_body())

    assert response.status_code == 200
    assert response.json()["turns_deleted"] == 0


def test_missing_user_profile_is_401(monkeypatch):
    _fake_answer_cache(monkeypatch)

    async def _fake_delete_conversation(conversation_id, employee_id):
        return 0

    monkeypatch.setattr(manage_conversations.conversation_memory, "delete_conversation", _fake_delete_conversation)

    response = client.request("DELETE", "/v1/conversations/conv-1", json={})

    assert response.status_code == 401


def test_list_conversations_returns_the_callers_own(monkeypatch):
    async def _fake_list_conversations(employee_id):
        assert employee_id == "EMP052"
        return [
            {
                "conversation_id": "conv-1",
                "title": "What is the dental plan?",
                "started_at": "2026-10-07T00:00:01Z",
                "last_updated_at": "2026-10-07T00:00:02Z",
            }
        ]

    monkeypatch.setattr(manage_conversations.conversation_memory, "list_conversations", _fake_list_conversations)

    response = client.get("/v1/conversations", params=EMPLOYEE_USER_PROFILE)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["conversations"][0]["conversation_id"] == "conv-1"


def test_list_conversations_missing_identity_is_401():
    response = client.get("/v1/conversations")

    assert response.status_code == 401


def test_get_conversation_returns_its_turns(monkeypatch):
    async def _fake_get_conversation_turns(conversation_id, employee_id):
        assert conversation_id == "conv-1"
        assert employee_id == "EMP052"
        return [
            {"role": "human", "content": "What is the dental plan?", "created_at": "2026-10-07T00:00:01Z"},
            {"role": "ai", "content": "Two options are available.", "created_at": "2026-10-07T00:00:02Z"},
        ]

    monkeypatch.setattr(
        manage_conversations.conversation_memory, "get_conversation_turns", _fake_get_conversation_turns
    )

    response = client.get("/v1/conversations/conv-1", params=EMPLOYEE_USER_PROFILE)

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "conv-1"
    assert len(body["turns"]) == 2
    assert body["turns"][0]["role"] == "human"


def test_get_someone_elses_conversation_returns_empty_turns(monkeypatch):
    async def _fake_get_conversation_turns(conversation_id, employee_id):
        return []

    monkeypatch.setattr(
        manage_conversations.conversation_memory, "get_conversation_turns", _fake_get_conversation_turns
    )

    response = client.get("/v1/conversations/not-mine", params=EMPLOYEE_USER_PROFILE)

    assert response.status_code == 200
    assert response.json()["turns"] == []
