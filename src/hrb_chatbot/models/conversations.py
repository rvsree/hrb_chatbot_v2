"""Request/response contracts for conversation data management (Phase 76)."""

from pydantic import BaseModel, Field


class ConversationDeleteResponse(BaseModel):
    conversation_id: str = Field(..., description="The conversation that was targeted for deletion.")
    turns_deleted: int = Field(
        ...,
        description="How many turns were actually deleted - 0 if the conversation didn't exist or belonged to someone else.",
    )
