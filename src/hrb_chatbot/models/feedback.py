"""Request/response contracts for feedback (Phase 104)."""

from pydantic import BaseModel, Field

from src.hrb_chatbot.common.enums import FeedbackVote
from src.hrb_chatbot.models.common import UserProfile


class FeedbackCreateRequest(BaseModel):
    user_profile: UserProfile | None = None
    conversation_id: str | None = Field(None, description="Null if conversation memory wasn't enabled for this chat.")
    message_id: str = Field(..., min_length=1, description="The UI's own id for the message this feedback is about.")
    vote: FeedbackVote
    reason_tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(None, max_length=2000)
    question: str = Field(..., min_length=1, description="The user's question this feedback is about - stored verbatim so a later view doesn't need a conversation-history lookup that doesn't exist yet.")
    answer: str = Field(..., min_length=1, description="The assistant's answer this feedback is about.")


class FeedbackRecord(BaseModel):
    id: int
    employee_id: str
    conversation_id: str | None
    message_id: str
    vote: str
    reason_tags: list[str]
    notes: str | None
    question: str
    answer: str
    created_at: str


class FeedbackCreateResponse(BaseModel):
    id: int


class FeedbackListResponse(BaseModel):
    count: int
    feedback: list[FeedbackRecord]
