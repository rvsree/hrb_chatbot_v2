"""Multi-agentic-rag - Planner Agent -> Orchestration Agent dispatch -> 4 domain
agents -> Reviewer Agent, via a real LangGraph graph. See
ai/agents/workflow_agents/multi_agent_pipeline.py and RAG-ROADMAP.md Phase 64."""

from fastapi import APIRouter, Request

from src.hrb_chatbot.ai.agents.workflow_agents import multi_agent_pipeline
from src.hrb_chatbot.ai.pre_processing.guardrails_input import GuardrailBlockedError
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.api.gateway.rbac import require_role
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.agentic_rag import ToolCallInfo
from src.hrb_chatbot.models.multi_agentic_rag import AgentTaskInfo, MultiAgenticRagRequest, MultiAgenticRagResponse

logger = get_logger("multi_agentic_rag.query_agent")

router_query_agent = APIRouter(tags=["multi-agentic-rag"])


@router_query_agent.post("/query", response_model=MultiAgenticRagResponse)
async def query(payload: MultiAgenticRagRequest, request: Request):
    userProfile = require_role(payload.user_profile, Role.EMPLOYEE, Role.MANAGER, Role.HR_SUPPORT)
    enforce_rate_limit(request)

    try:
        result = await multi_agent_pipeline.run_multi_agent(
            payload.query,
            userProfile.employee_id,
            enable_conversation_memory=payload.enable_conversation_memory,
            conversation_id=payload.conversation_id,
        )
    except GuardrailBlockedError as error:
        return json_error(422, str(error), code=error_codes.INPUT_GUARDRAIL_BLOCKED)

    return MultiAgenticRagResponse(
        query=payload.query,
        answer=result["answer"],
        tasks=[AgentTaskInfo(**task) for task in result["tasks"]],
        tools_used=[ToolCallInfo(**call) for call in result["tools_used"]],
        iterations=result["iterations"],
        conversation_id=result.get("conversation_id"),
    )
