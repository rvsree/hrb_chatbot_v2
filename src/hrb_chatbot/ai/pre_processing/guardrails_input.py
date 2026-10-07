"""Checks a query against NeMo Guardrails' input rails before retrieval -
Gate 1 (Firewall) of the six-gate validation pattern. See RAG-ROADMAP.md Phase 7."""

from pathlib import Path

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import RailStatus, RailType

from src.hrb_chatbot.ai.pre_processing.safe_terms import protect_known_safe_terms
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("guardrails_input")

CONFIG_PATH = Path(__file__).resolve().parents[1] / "guardrails_config"

_rails = None


def get_rails() -> LLMRails:
    """Load the guardrails config once and reuse it - matches the lazy,
    cached singleton pattern this project's other gateways already use."""
    global _rails
    if _rails is None:
        config = RailsConfig.from_path(str(CONFIG_PATH))
        _rails = LLMRails(config)
    return _rails


class GuardrailBlockedError(Exception):
    """Raised when a guardrail blocks a query - the route turns this into a 422."""


async def check_input(query: str) -> str:
    """Runs input rails on the query. Returns the query to actually use
    (masked if NeMo redacted PII). Raises GuardrailBlockedError if blocked."""
    protected_query = protect_known_safe_terms(query)
    result = await get_rails().check_async([{"role": "user", "content": protected_query}], rail_types=[RailType.INPUT])

    if result.status == RailStatus.BLOCKED:
        logger.warning("Input blocked by guardrail %s", result.rail)
        raise GuardrailBlockedError(f"This request was blocked by a safety check ({result.rail}).")

    if result.status == RailStatus.MODIFIED:
        logger.info("Input modified by guardrail - sensitive data masked")

    return result.content
