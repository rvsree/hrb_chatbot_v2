"""Request/response contracts for conversation data management (Phase 76/116)."""

from pydantic import BaseModel, Field


class ConversationDeleteResponse(BaseModel):
    conversation_id: str = Field(..., description="The conversation that was targeted for deletion.")
    turns_deleted: int = Field(
        ...,
        description="How many turns were actually deleted - 0 if the conversation didn't exist or belonged to someone else.",
    )


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str = Field(..., description="The conversation's first human turn, verbatim.")
    started_at: str
    last_updated_at: str


class ConversationListResponse(BaseModel):
    count: int
    conversations: list[ConversationSummary]


class ConversationTurn(BaseModel):
    role: str = Field(..., description="'human' or 'ai'.")
    content: str
    created_at: str


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    turns: list[ConversationTurn]
