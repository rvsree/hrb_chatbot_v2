"""Vector KB Agent - multi-agentic-rag's domain agent over the policy knowledge base.
Thin wrapper, no new logic: reuses single-agentic-rag's existing search tool as-is."""

from src.hrb_chatbot.ai.rag_pipeline.tools.agentic_tools import search_knowledge_base


async def run(focus: str) -> tuple[str, list[dict]]:
    return await search_knowledge_base(focus)
