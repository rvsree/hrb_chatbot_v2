"""Role-based access check - called explicitly at the top of every route,
against an already-resolved UserProfile (Phase 45: identity resolution
itself lives in user_profile.py, since its source now differs by endpoint)."""

from fastapi import HTTPException

from src.hrb_chatbot.api.gateway.user_profile import UserProfile
from src.hrb_chatbot.common.enums import Role


def check_role(userProfile: UserProfile, *allowed_roles: Role) -> UserProfile:
    """Raise 403 unless userProfile's role is one of allowed_roles."""
    if userProfile.role not in allowed_roles:
        allowed = [role.value for role in allowed_roles]
        raise HTTPException(
            status_code=403,
            detail=f"Role {userProfile.role!r} is not permitted here - requires one of {allowed}",
        )
    return userProfile
