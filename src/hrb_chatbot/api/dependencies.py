"""Shared request parameters and response helpers for the routers in this folder."""

from fastapi import Query
from fastapi.responses import JSONResponse

from src.hrb_chatbot.common.enums import LlmProvider, MetadataStore, VectorDB

# Query()'s enum default (e.g. LlmProvider.OPENAI) is what makes /docs render these
# as a dropdown of the allowed values instead of a free-text box - and what makes
# FastAPI reject a typo with a 422 before check_all_backend_services() ever runs,
# instead of the typo silently falling through to a default deep inside it.
PROVIDER_QUERY = Query(
    default=LlmProvider.OPENAI,
    description="Which LLM provider to check.",
)

METADATA_PROVIDER_QUERY = Query(
    default=MetadataStore.SQLITE,
    description=(
        "Which document-metadata store to check: 'sqlite' (the active store) "
        "or 'postgres' (a fully working alternative, not yet the active one)."
    ),
)

VECTOR_PROVIDER_QUERY = Query(
    default=VectorDB.CHROMADB,
    description=(
        "Which vector store to check: 'chromadb' (the active store) or "
        "'pinecone' (a fully working alternative, not yet the active one - "
        "checking it will create the configured index on first call if it "
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
