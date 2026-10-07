"""Checks a generated answer against NeMo Guardrails' output rails (Gate 6) - faithfulness is DeepEval's job."""

from src.hrb_chatbot.ai.pre_processing.guardrails_input import get_rails
from src.hrb_chatbot.ai.pre_processing.safe_terms import protect_known_safe_terms
from src.hrb_chatbot.common.logging.logger import get_logger
from nemoguardrails.rails.llm.options import RailStatus, RailType

logger = get_logger("guardrails_output")

SAFE_FALLBACK_ANSWER = "I'm not able to share that response. Please rephrase your question."


async def check_output(query: str, answer: str) -> str:
    """Runs output rails - returns masked text if PII was redacted, or a safe fallback if blocked."""
    protected_answer = protect_known_safe_terms(answer)
    messages = [{"role": "user", "content": query}, {"role": "assistant", "content": protected_answer}]
    result = await get_rails().check_async(messages, rail_types=[RailType.OUTPUT])

    if result.status == RailStatus.BLOCKED:
        logger.warning("Output blocked by guardrail %s", result.rail)
        return SAFE_FALLBACK_ANSWER

    if result.status == RailStatus.MODIFIED:
        logger.info("Output modified by guardrail - sensitive data masked")

    return result.content
