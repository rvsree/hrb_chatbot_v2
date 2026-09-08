"""Ask the knowledge base a question - free to call, but the underlying
pipeline spends real money once Phase 6 replaces its stub (an embedding
call and a chat completion per query).

The pipeline itself (ai/rag_pipeline/pipeline.py) is hand-written and not
implemented yet - this endpoint's job is only to validate the request, call
the entry point, and turn whatever happens into a clear response. 501 here
means "not built yet", not "broken" - same convention as the indexing
endpoint before it was implemented.

Rate limiting and Idempotency-Key support are wired in now (see
routes_documents.py's module docstring for the fuller reasoning) even
though the endpoint is still a stub - so the pattern is already in place
and tested by the time Phase 6 makes it matter. **Not** wired in yet: the
pre-flight backend-config check routes_documents.py's index_document()
has. Adding it here now would gate this stub behind a real OPENAI_API_KEY
being configured, breaking in exactly the environment that most needs this
endpoint testable without one - CI, which runs with no secrets at all (see
docs/AWS-DEVOPS-RUNBOOK.md's CI workflow). Add the same preflight check
here once this endpoint makes a real backend call for the first time, not
before - a config gate in front of a guaranteed NotImplementedError
protects nothing.
"""

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common.idempotency.idempotency_store import get_idempotency_store
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.rag import RagQueryRequest, RagQueryResponse
from src.hrb_chatbot.services import rag_service

logger = get_logger("routes_query")

router = APIRouter(prefix="/rag", tags=["query"])


@router.post("/query", response_model=RagQueryResponse, dependencies=[Depends(enforce_rate_limit)])
async def query(
    payload: RagQueryRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Ask a question and get back a grounded answer with its sources.

    Pass an `Idempotency-Key` header to make a retry of this exact call
    safe once this endpoint spends real money (Phase 6) - replaying the
    same key returns the same answer instead of paying for a second
    embedding + generation call for a question that was already answered.
    """
    store = get_idempotency_store()
    if idempotency_key:
        cached = store.get(idempotency_key)
        if cached is not None:
            status_code, body = cached
            return JSONResponse(status_code=status_code, content=body)

    try:
        result = await rag_service.answer_query(
            payload.query,
            top_k=payload.top_k,
            vector_db=payload.vector_db,
            model_name=payload.model_name,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except NotImplementedError as error:
        # str(error) here is a controlled, deliberately-written message
        # from the stub functions themselves (see ai/rag_pipeline/pipeline.py)
        # naming exactly which module to implement - safe and useful to
        # show a caller, unlike the generic Exception case below.
        return json_error(501, str(error))
    except Exception as error:
        # Full detail server-side only - never in the client-facing
        # response. See routes_documents.py's module docstring for the
        # same reasoning applied there.
        logger.error("Query failed for %r: %s: %s", payload.query, type(error).__name__, error)
        return json_error(500, "The query could not be answered. Please try again.")

    response = RagQueryResponse(**result)

    if idempotency_key:
        store.set(idempotency_key, 200, response.model_dump())

    return response
