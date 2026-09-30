"""Shared request parameters and response helpers for the routers in this folder."""

from fastapi import Query
from fastapi.responses import JSONResponse

from src.hrb_chatbot.common.enums import LlmProvider, MetadataStore, VectorDB

# Query()'s enum default makes /docs render a dropdown and rejects a typo with a 422 before any check runs.
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
    """Build a consistent error shape: {"error": ..., "code": ..., ...extra}."""
    body = {"error": message, "code": code}
    body.update(extra)
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def health_response(report: dict) -> JSONResponse:
    """Turn a health report into a response - 200 when healthy, 503 otherwise."""
    if report["status"] == "healthy":
        status_code = 200
    else:
        status_code = 503
    return JSONResponse(content=report, status_code=status_code)
