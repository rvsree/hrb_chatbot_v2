"""Shapes shared across more than one endpoint's request/response contract."""

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    employee_id: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=200)
    role: str = Field(..., max_length=50)


class IdentityPayload(BaseModel):
    """The JSON body for GET/DELETE endpoints - identity only, deliberately never a query param or header."""

    user_profile: UserProfile | None = None
