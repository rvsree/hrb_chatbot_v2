"""Tests for POST /v1/auth/login (Phase 106)."""

from fastapi.testclient import TestClient

from src.hrb_chatbot.main import app

client = TestClient(app)


def test_known_combo_returns_200_with_the_matched_profile():
    response = client.post(
        "/v1/auth/login", json={"employee_id": "EMP052", "full_name": "Eddy Employee", "role": "employee"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_profile": {"employee_id": "EMP052", "full_name": "Eddy Employee", "role": "employee"}
    }


def test_unknown_employee_id_is_401():
    response = client.post(
        "/v1/auth/login", json={"employee_id": "EMP999", "full_name": "Nobody", "role": "employee"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNKNOWN_PERSONA"


def test_right_employee_id_wrong_role_is_401():
    response = client.post(
        "/v1/auth/login", json={"employee_id": "EMP052", "full_name": "Eddy Employee", "role": "hr_support"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNKNOWN_PERSONA"
