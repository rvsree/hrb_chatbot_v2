"""Runs a query through the RAG pipeline - thin wrapper so the router
doesn't import from ai/ directly."""

from src.hrb_chatbot.ai.rag_pipeline import pipeline
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rag_query_params import RagQueryParams

logger = get_logger("rag_service")


async def answer_query(params: RagQueryParams) -> dict:
    """Run the full RAG pipeline for one question: decompose, retrieve, generate."""
    return await pipeline.answer_query(params)
