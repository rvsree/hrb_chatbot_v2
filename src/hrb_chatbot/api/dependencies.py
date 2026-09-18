"""Shared request parameters and response helpers for the routers in this folder."""

from fastapi import Query
from fastapi.responses import JSONResponse

from src.hrb_chatbot.common.enums import LlmProvider, MetadataStore, VectorDB

# Query()'s enum default is what makes /docs render a dropdown, and what
# makes FastAPI reject a typo with a 422 before any check runs.
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
    """Build a consistent error shape: {"error": ..., "code": ..., ...extra}.
    `code` is required (from common/error_codes.py), never defaulted.
    `headers` becomes real HTTP headers, kept separate so it can't leak into the body."""
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
