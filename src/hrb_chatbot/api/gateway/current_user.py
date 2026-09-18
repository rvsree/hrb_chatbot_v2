"""Resolves who's calling the API - a placeholder for real OAuth (Phase 23),
not authentication. Reads three plain, unsigned request headers as-is; the
point is the dependency-injection seam (get_current_user -> require_role)
real auth will slot into later, not real security today."""

from dataclasses import dataclass

from fastapi import HTTPException, Request

from src.hrb_chatbot.common.enums import Role

EMPLOYEE_ID_HEADER = "X-Employee-Id"
FULL_NAME_HEADER = "X-Full-Name"
ROLE_HEADER = "X-Role"


@dataclass
class CurrentUser:
    """Who's calling - employee_id/full_name are audit metadata only,
    never part of the access-control decision; role is what gates access."""

    employee_id: str
    full_name: str
    role: Role


def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency - resolves CurrentUser from request headers, or
    raises 401. Fails closed: all three headers are required, not defaulted."""
    employee_id = request.headers.get(EMPLOYEE_ID_HEADER)
    full_name = request.headers.get(FULL_NAME_HEADER)
    role_value = request.headers.get(ROLE_HEADER)

    missing_headers = [
        name
        for name, value in ((EMPLOYEE_ID_HEADER, employee_id), (FULL_NAME_HEADER, full_name), (ROLE_HEADER, role_value))
        if not value
    ]
    if missing_headers:
        raise HTTPException(
            status_code=401, detail=f"Missing required identity header(s): {', '.join(missing_headers)}"
        )

    try:
        role = Role(role_value)
    except ValueError:
        valid_roles = [member.value for member in Role]
        raise HTTPException(status_code=401, detail=f"Unknown {ROLE_HEADER} {role_value!r} - choose one of {valid_roles}")

    return CurrentUser(employee_id=employee_id, full_name=full_name, role=role)
