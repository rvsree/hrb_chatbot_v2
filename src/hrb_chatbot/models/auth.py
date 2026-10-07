"""Request/response contracts for login validation (Phase 106)."""

from pydantic import BaseModel, Field

from src.hrb_chatbot.models.common import UserProfile


class LoginRequest(BaseModel):
    employee_id: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=200)
    role: str = Field(..., max_length=50)


class LoginResponse(BaseModel):
    user_profile: UserProfile
