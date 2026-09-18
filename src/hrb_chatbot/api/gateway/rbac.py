"""Role-based access check - wired at the router level in main.py, so
routes_documents.py/routes_query.py never see this directly."""

from fastapi import Depends, HTTPException

from src.hrb_chatbot.api.gateway.current_user import CurrentUser, get_current_user
from src.hrb_chatbot.common.enums import Role


def require_role(*allowed_roles: Role):
    """Return a FastAPI dependency raising 403 unless the caller's resolved
    role is one of allowed_roles. Depends on get_current_user for who's calling."""

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            allowed = [role.value for role in allowed_roles]
            raise HTTPException(
                status_code=403,
                detail=f"Role {current_user.role.value!r} is not permitted here - requires one of {allowed}",
            )
        return current_user

    return _check
