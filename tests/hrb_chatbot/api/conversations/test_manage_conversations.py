"""Tests for DELETE /v1/conversations/{conversation_id} (Phase 76) -
conversation_memory.delete_conversation() is faked, no real database."""

from fastapi.testclient import TestClient

from src.hrb_chatbot.api.conversations import manage_conversations
from src.hrb_chatbot.main import app

client = TestClient(app)

EMPLOYEE_USER_PROFILE = {"employee_id": "EMP052", "full_name": "Eddy Employee", "role": "employee"}


def _body(user_profile=None) -> dict:
    return {"user_profile": EMPLOYEE_USER_PROFILE if user_profile is None else user_profile}


def test_well_formed_request_returns_turns_deleted(monkeypatch):
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
    async def _fake_delete_conversation(conversation_id, employee_id):
        return 0

    monkeypatch.setattr(manage_conversations.conversation_memory, "delete_conversation", _fake_delete_conversation)

    response = client.request("DELETE", "/v1/conversations/not-mine", json=_body())

    assert response.status_code == 200
    assert response.json()["turns_deleted"] == 0


def test_missing_user_profile_is_401(monkeypatch):
    async def _fake_delete_conversation(conversation_id, employee_id):
        return 0

    monkeypatch.setattr(manage_conversations.conversation_memory, "delete_conversation", _fake_delete_conversation)

    response = client.request("DELETE", "/v1/conversations/conv-1", json={})

    assert response.status_code == 401
