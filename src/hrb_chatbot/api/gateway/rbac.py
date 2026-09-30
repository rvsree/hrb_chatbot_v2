"""Identity + role check for every route - 401 for a missing/invalid identity, 403 for the wrong role."""

from fastapi import HTTPException

from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.models.common import UserProfile


def require_role(user_profile: UserProfile | None, *allowed_roles: Role) -> UserProfile:
    if user_profile is None:
        raise HTTPException(status_code=401, detail="Missing required user_profile in the request payload")

    try:
        Role(user_profile.role)
    except ValueError:
        valid_roles = [member.value for member in Role]
        raise HTTPException(status_code=401, detail=f"Unknown role {user_profile.role!r} - choose one of {valid_roles}")

    if user_profile.role not in allowed_roles:
        allowed = [role.value for role in allowed_roles]
        raise HTTPException(
            status_code=403,
            detail=f"Role {user_profile.role!r} is not permitted here - requires one of {allowed}",
        )
    return user_profile
