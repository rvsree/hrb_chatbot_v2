"""Reviewer Agent - multi-agentic-rag's merge step. 0/1/2+ branching matches the
IK FDE Travel Planner reference notebook's own synthesizer_node() pattern."""

import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.hrb_chatbot.ai.agents._llm_helpers import AGENT_LLM_TIMEOUT_SECONDS, build_agent_llm
from src.hrb_chatbot.ai.pre_processing.context_builder import build_context_from_agent_results
from src.hrb_chatbot.ai.prompts.agent_prompts import REVIEWER_SYSTEM_PROMPT
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("agents.reviewer_agent")


def _build_llm() -> ChatOpenAI:
    return build_agent_llm()


async def review(query: str, agent_results: list[dict]) -> str:
    """Merges every domain agent's result into one final answer."""
    if not agent_results:
        return "I wasn't able to find an answer to that question."

    if len(agent_results) == 1:
        return agent_results[0]["result"]

    combined = build_context_from_agent_results(agent_results)
    llm = _build_llm()
    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=f"Original question: {query}\n\nDomain agent results:\n{combined}"),
    ]

    with log_backend_call(logger, "reviewer_agent", "review"):
        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=AGENT_LLM_TIMEOUT_SECONDS)

    if response.usage_metadata:
        logger.info(
            "[reviewer_agent] tokens used: %s prompt + %s completion",
            response.usage_metadata["input_tokens"],
            response.usage_metadata["output_tokens"],
        )

    return response.content
