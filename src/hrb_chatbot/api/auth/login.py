"""Phase 106 - lightweight login validation. Denies an employee_id/
full_name/role combo that isn't in the known-personas roster, instead of
accepting anything typed into the login form. Still not real
authentication - role stays self-asserted on every request after this,
unchanged from this project's documented RBAC-is-a-formality design."""

from fastapi import APIRouter

from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.known_personas import is_known_persona
from src.hrb_chatbot.models.auth import LoginRequest, LoginResponse
from src.hrb_chatbot.models.common import UserProfile

router_login = APIRouter(tags=["auth"])


@router_login.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    if not is_known_persona(payload.employee_id, payload.full_name, payload.role):
        return json_error(
            401,
            f"{payload.employee_id!r} isn't a known persona for this demo - check the id, name, and role.",
            code=error_codes.UNKNOWN_PERSONA,
        )

    return LoginResponse(
        user_profile=UserProfile(employee_id=payload.employee_id, full_name=payload.full_name, role=payload.role)
    )
