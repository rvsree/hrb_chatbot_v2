"""Request/response contracts for single-agentic-rag (Phase 55) - same
Phase 45 identity-via-payload pattern as models/rag.py, not headers."""

from pydantic import BaseModel, Field

from src.hrb_chatbot.models.common import ToolCallInfo, UserProfile
from src.hrb_chatbot.models.rag import ExplainabilityInfo, RetrievedChunk


class AgenticRagRequest(BaseModel):
    user_profile: UserProfile | None = None
    query: str = Field(..., min_length=1, max_length=2000, description="The question to ask the agent.")
    max_iterations: int | None = Field(
        None, ge=1, le=10, description="Upper bound on tool-call rounds before giving up - defaults to 5, matching the course reference."
    )
    enable_conversation_memory: bool = Field(
        False, description="Carry conversation history across calls, server-side, keyed by conversation_id."
    )
    conversation_id: str | None = Field(
        None,
        description="Pass back the value from a prior response to continue that conversation. Ignored if "
        "enable_conversation_memory is false; a new one is generated if true and this is omitted.",
    )



class AgenticRagResponse(BaseModel):
    """What POST /query returns."""

    query: str = Field(..., description="The question that was asked.")
    answer: str = Field(..., description="The agent's final answer.")
    tools_used: list[ToolCallInfo] = Field(..., description="Every tool call the agent made, in order.")
    sources: list[RetrievedChunk] = Field(
        default_factory=list, description="Phase 115 - real chunks from SearchKnowledgeBase calls, if any."
    )
    iterations: int = Field(..., description="How many reasoning rounds the agent actually took.")
    explainability_info: ExplainabilityInfo = Field(..., description="Phase 110 - same shape as genai-rag's own.")
    conversation_id: str | None = Field(
        None,
        description="Echoed/generated when enable_conversation_memory was true - pass it back on the next "
        "call to continue this conversation. Null when memory wasn't enabled.",
    )
