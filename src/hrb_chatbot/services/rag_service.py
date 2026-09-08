"""Runs a query through the RAG pipeline.

Thin on purpose: the actual decompose/retrieve/generate logic lives in
ai/rag_pipeline/pipeline.py (a scaffold today, hand-written logic once
Phase 6 lands - see docs/RAG-ROADMAP.md). This file exists so the router
doesn't import from ai/ directly, matching documents_service.py's own
relationship to ai/doc_processing/pipeline.py.
"""

from src.hrb_chatbot.ai.rag_pipeline import pipeline
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rag_service")


async def answer_query(query: str, top_k: int = 5, vector_db: str | None = None) -> dict:
    """Run the full RAG pipeline for one question. Raises NotImplementedError
    until Phase 6 exists - the router turns that into a 501, not a crash."""
    return await pipeline.answer_query(query, top_k=top_k, vector_db=vector_db)
