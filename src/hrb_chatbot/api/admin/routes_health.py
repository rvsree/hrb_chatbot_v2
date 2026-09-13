"""The health endpoints - free, and the first thing to check when anything is odd."""

from fastapi import APIRouter

from src.hrb_chatbot.api.admin import health_checks as agent_health
from src.hrb_chatbot.api.dependencies import (
    DEEP_QUERY,
    METADATA_PROVIDER_QUERY,
    PROVIDER_QUERY,
    VECTOR_PROVIDER_QUERY,
    health_response,
)

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(
    provider: str = PROVIDER_QUERY,
    deep: bool = DEEP_QUERY,
    metadata_provider: str = METADATA_PROVIDER_QUERY,
    vector_provider: str = VECTOR_PROVIDER_QUERY,
):
    """Check every backend integration this app currently has wired up:
    the LLM client, the vector store, and the document-metadata store.
    """
    return health_response(
        agent_health.check_all_backend_services(
            provider=provider,
            deep=deep,
            metadata_provider=metadata_provider,
            vector_provider=vector_provider,
        )
    )
