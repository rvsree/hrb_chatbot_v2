"""Checks a generated answer against NeMo Guardrails' output rails -
Gate 6 (Delivery Gate). Faithfulness (Gate 5) is DeepEval's job, not
NeMo's - see RAG-ROADMAP.md Phase 7's scope cut."""

from src.hrb_chatbot.ai.pre_processing.guardrails_input import get_rails
from src.hrb_chatbot.common.logging.logger import get_logger
from nemoguardrails.rails.llm.options import RailStatus, RailType

logger = get_logger("guardrails_output")

SAFE_FALLBACK_ANSWER = "I'm not able to share that response. Please rephrase your question."


async def check_output(query: str, answer: str) -> str:
    """Runs output rails on the answer. Returns the answer to actually
    return (masked if NeMo redacted PII, or a safe fallback if blocked)."""
    messages = [{"role": "user", "content": query}, {"role": "assistant", "content": answer}]
    result = await get_rails().check_async(messages, rail_types=[RailType.OUTPUT])

    if result.status == RailStatus.BLOCKED:
        logger.warning("Output blocked by guardrail %s", result.rail)
        return SAFE_FALLBACK_ANSWER

    if result.status == RailStatus.MODIFIED:
        logger.info("Output modified by guardrail - sensitive data masked")

    return result.content
