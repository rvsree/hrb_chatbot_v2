"""The health endpoints.

GET /ping - free, instant, no provider calls. This is what a container
HEALTHCHECK or a deploy's smoke test should point at (see the Dockerfile and
.github/workflows/deploy.yml) - it only answers "is the process up and
serving requests", which is all an automated probe running every 30 seconds
forever should ever need to know.

GET /health - the real diagnostic: it actually calls each backend (the LLM
provider, the vector store, the document-metadata store) and reports whether
each one is truly reachable, not just "configured". That real call is exactly
why this is a separate endpoint from /ping - a probe firing every 30 seconds
must never be the thing spending API tokens or getting rate-limited.
"""

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
