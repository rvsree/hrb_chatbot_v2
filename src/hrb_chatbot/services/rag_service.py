"""Runs a query through the RAG pipeline.

Thin on purpose: the real decompose/retrieve/generate logic lives in
ai/rag_pipeline/pipeline.py. This file exists only so the router doesn't
import from ai/ directly.
"""

from src.hrb_chatbot.ai.rag_pipeline import pipeline
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_service")


async def answer_query(
    query: str,
    top_k: int = 5,
    vector_db: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict:
    """Run the full RAG pipeline for one question. Raises NotImplementedError
    until Phase 6 exists - the router turns that into a 501, not a crash."""
    return await pipeline.answer_query(
        query,
        top_k=top_k,
        vector_db=vector_db,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
