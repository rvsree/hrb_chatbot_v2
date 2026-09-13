"""Shared request parameters and response helpers for the routers in this folder."""

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


def json_error(
    status_code: int, message: str, code: str, headers: dict | None = None, **extra
) -> JSONResponse:
    """Build an error response with a consistent shape: {"error": "...", "code": "...", ...extra}.
    `code` is required, not optional-with-a-default - every call site must
    pick one from common/error_codes.py, on purpose, rather than one being
    silently forgotten. `message` can change wording freely; `code` is the
    stable part a caller should actually branch on. `headers` becomes real
    HTTP response headers (e.g. Retry-After) - kept separate from `extra`
    so it can never accidentally leak into the JSON body instead."""
    body = {"error": message, "code": code}
    body.update(extra)
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def health_response(report: dict) -> JSONResponse:
    """Turn a health report into a response with the right status code - 200 when
    healthy, 503 otherwise, since a monitoring tool reads the status code, not the body."""
    if report["status"] == "healthy":
        status_code = 200
    else:
        status_code = 503
    return JSONResponse(content=report, status_code=status_code)
