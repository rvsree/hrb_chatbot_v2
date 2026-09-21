"""Resolves who's calling the API - a placeholder for real OAuth (Phase 23),
not authentication. Phase 45: identity comes from a JSON request body's
user_profile sub-object, on every endpoint including GET/DELETE, never
headers or query params - see docs/endpoint-request-response-contracts.md."""

from fastapi import HTTPException

from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.models.common import UserProfile


def resolve_user_from_profile(user_profile: UserProfile | None) -> UserProfile:
    """Fails closed (401) if user_profile is missing, or its role isn't a
    real Role value - an identity problem, not a generic payload problem."""
    if user_profile is None:
        raise HTTPException(status_code=401, detail="Missing required user_profile in the request payload")

    try:
        Role(user_profile.role)
    except ValueError:
        valid_roles = [member.value for member in Role]
        raise HTTPException(
            status_code=401, detail=f"Unknown role {user_profile.role!r} - choose one of {valid_roles}"
        )

    return user_profile
