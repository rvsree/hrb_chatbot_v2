"""Tests for require_role() (api/gateway/rbac.py) - identity + role check used at every route."""

import pytest
from fastapi import HTTPException

from src.hrb_chatbot.api.gateway.rbac import require_role
from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.models.common import UserProfile


def test_missing_user_profile_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        require_role(None, Role.HR_SUPPORT)

    assert exc_info.value.status_code == 401


def test_unknown_role_raises_401():
    profile = UserProfile(employee_id="EMP052", full_name="Eddy Employee", role="made-up-role")

    with pytest.raises(HTTPException) as exc_info:
        require_role(profile, Role.HR_SUPPORT)

    assert exc_info.value.status_code == 401


def test_valid_identity_wrong_role_raises_403():
    profile = UserProfile(employee_id="EMP052", full_name="Eddy Employee", role="employee")

    with pytest.raises(HTTPException) as exc_info:
        require_role(profile, Role.HR_SUPPORT)

    assert exc_info.value.status_code == 403


def test_valid_identity_allowed_role_returns_the_user_profile():
    profile = UserProfile(employee_id="EMP051", full_name="Hana Support", role="hr_support")

    result = require_role(profile, Role.HR_SUPPORT)

    assert result is profile
