"""Single-agentic-rag - a tool-calling agent, not a fixed retrieve-then-generate pipeline."""

from fastapi import APIRouter, Request

from src.hrb_chatbot.ai.agents.workflow_agents.orchestration_agent import run_agent
from src.hrb_chatbot.api.gateway.rbac import require_role
from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.agentic_rag import AgenticRagRequest, AgenticRagResponse, ToolCallInfo

logger = get_logger("query_agent")

router_query_agent = APIRouter(tags=["single-agentic-rag"])


@router_query_agent.post("/query", response_model=AgenticRagResponse)
async def query(payload: AgenticRagRequest, request: Request):
    userProfile = require_role(payload.user_profile, Role.EMPLOYEE, Role.MANAGER, Role.HR_SUPPORT)
    enforce_rate_limit(request)

    result = await run_agent(
        payload.query,
        userProfile.employee_id,
        payload.max_iterations,
        enable_conversation_memory=payload.enable_conversation_memory,
        conversation_id=payload.conversation_id,
    )

    return AgenticRagResponse(
        query=payload.query,
        answer=result["answer"],
        tools_used=[ToolCallInfo(**call) for call in result["tools_used"]],
        iterations=result["iterations"],
        conversation_id=result.get("conversation_id"),
    )
