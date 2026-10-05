"""Delete a caller's own conversation history - the NFR data-management
endpoint (Phase 76). Calls ai/pre_processing/conversation_memory.py
directly, same precedent as retrieve_document.py - no service layer, since
there's no logic beyond the one function call (rag_service.py was removed
for exactly this reason - a pass-through with no logic of its own)."""

from fastapi import APIRouter, Request

from src.hrb_chatbot.ai.pre_processing import conversation_memory
from src.hrb_chatbot.api.gateway.rbac import require_role
from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.common import IdentityPayload
from src.hrb_chatbot.models.conversations import ConversationDeleteResponse

logger = get_logger("conversations.manage_conversations")

router_manage_conversations = APIRouter(tags=["conversations"])


@router_manage_conversations.delete("/{conversation_id}", response_model=ConversationDeleteResponse)
async def delete_conversation(conversation_id: str, identity: IdentityPayload, request: Request):
    """Deletes every turn for one conversation - scoped to the caller's own employee_id,
    so one employee can never delete another's history even by knowing their conversation_id."""
    userProfile = require_role(identity.user_profile, Role.EMPLOYEE, Role.MANAGER, Role.HR_SUPPORT)
    await enforce_rate_limit(request)

    turns_deleted = await conversation_memory.delete_conversation(conversation_id, userProfile.employee_id)

    return ConversationDeleteResponse(conversation_id=conversation_id, turns_deleted=turns_deleted)
