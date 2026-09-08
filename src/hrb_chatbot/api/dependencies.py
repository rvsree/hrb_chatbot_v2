"""Shared request parameters and response helpers for the routers in this folder.

Declared once here so a description doesn't drift between endpoints that share
the same query parameter - see the health router, which uses both DEEP_QUERY and
PROVIDER_QUERY.
"""

from fastapi import Query
from fastapi.responses import JSONResponse

DEEP_QUERY = Query(
    default=False,
    description=(
        "Also send one real but free request to the provider, to prove the API key "
        "and base URL work. Leave it off to only check that the settings are present."
    ),
)

PROVIDER_QUERY = Query(
    default="openai",
    description="Which LLM provider to check: 'openai', 'anthropic', 'openrouter' or 'bedrock'.",
)

METADATA_PROVIDER_QUERY = Query(
    default="sqlite",
    description=(
        "Which document-metadata store to check: 'sqlite' (the active store) "
        "or 'postgres' (a fully working alternative, not yet the active one)."
    ),
)

VECTOR_PROVIDER_QUERY = Query(
    default="chromadb",
    description=(
        "Which vector store to check: 'chromadb' (the active store) or "
        "'pinecone' (a fully working alternative, not yet the active one - "
        "deep=true will create the configured index on first call if it "
        "doesn't exist yet)."
    ),
)


def json_error(status_code: int, message: str, **extra) -> JSONResponse:
    """Build an error response with a consistent shape: {"error": "...", ...extra}."""
    body = {"error": message}
    body.update(extra)
    return JSONResponse(status_code=status_code, content=body)


def health_response(report: dict) -> JSONResponse:
    """Turn a health report into a response with the right status code.

    200 when the report says healthy, 503 when it does not - a monitoring tool
    watches the status code and never reads the body.
    """
    status_code = 200 if report["status"] == "healthy" else 503
    return JSONResponse(content=report, status_code=status_code)
