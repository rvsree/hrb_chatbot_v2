"""The health endpoints - free, and the first thing to check when anything is odd.

Both of these answer with 503 rather than 200 when something is wrong. That is
the contract a container orchestrator relies on: ECS, Kubernetes and Docker
Compose all decide whether to keep a task in the load balancer by looking at the
status code alone, and none of them read the body.

`GET /health` is what a liveness or readiness probe should point at. Leave `deep`
off when you do: the shallow check is instant and touches no network, so probing
it every ten seconds costs nothing. `?deep=true` makes one free provider call and
is for a human debugging a key, not for a probe.
"""

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

    Returns 503 (Service Unavailable) rather than 200 when something is
    wrong, so a monitoring tool notices without having to read the JSON.
    """
    return health_response(
        agent_health.check_everything(
            provider=provider,
            deep=deep,
            metadata_provider=metadata_provider,
            vector_provider=vector_provider,
        )
    )
