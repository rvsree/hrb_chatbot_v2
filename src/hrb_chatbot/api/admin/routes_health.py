"""The health endpoints - GET /ping is free/instant, GET /health calls each backend for real."""

from fastapi import APIRouter

from src.hrb_chatbot.api.admin import health_checks as agent_health
from src.hrb_chatbot.api.dependencies import (
    METADATA_PROVIDER_QUERY,
    PROVIDER_QUERY,
    VECTOR_PROVIDER_QUERY,
    health_response,
)
from src.hrb_chatbot.common.enums import LlmProvider, MetadataStore, VectorDB

router = APIRouter(tags=["health"])


@router.get("/ping")
def ping():
    """Confirm the process is up - no provider is called, so this never fails on a down backend."""
    return {"status": "ok"}


@router.get("/health")
def get_health(
    provider: LlmProvider = PROVIDER_QUERY,
    metadata_provider: MetadataStore = METADATA_PROVIDER_QUERY,
    vector_provider: VectorDB = VECTOR_PROVIDER_QUERY,
):
    """Check every backend integration (LLM, vector store, metadata store) with one real, free call each."""
    return health_response(
        agent_health.check_all_backend_services(
            provider=provider,
            metadata_provider=metadata_provider,
            vector_provider=vector_provider,
        )
    )
