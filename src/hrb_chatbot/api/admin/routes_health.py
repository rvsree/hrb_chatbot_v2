"""The health endpoints. GET /ping - free, instant, no provider calls (what
a container HEALTHCHECK/deploy smoke test should point at). GET /health -
the real diagnostic, actually calls each backend and reports reachability."""

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
    """Confirm the process is up and serving requests - nothing more. No
    provider is called, so this never fails because a backend is down; use
    GET /health for that."""
    return {"status": "ok"}


@router.get("/health")
def get_health(
    provider: LlmProvider = PROVIDER_QUERY,
    metadata_provider: MetadataStore = METADATA_PROVIDER_QUERY,
    vector_provider: VectorDB = VECTOR_PROVIDER_QUERY,
):
    """Check every backend integration this app currently has wired up:
    the LLM client, the vector store, and the document-metadata store.
    Each check makes one real, free call to its backend - see health_checks.py.
    """
    return health_response(
        agent_health.check_all_backend_services(
            provider=provider,
            metadata_provider=metadata_provider,
            vector_provider=vector_provider,
        )
    )
