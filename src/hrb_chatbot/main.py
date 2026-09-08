from fastapi import FastAPI, Request

from src.hrb_chatbot.api.admin import routes_health
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.api.rag import routes_documents, routes_query
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title="HRB Chatbot",
    version="0.1.0",
    description="An HR benefits chatbot backed by a RAG pipeline over the JPMC benefits knowledge base.",
)

# Routers are added here as each feature lands, one at a time.
#
# /health is deliberately NOT versioned - a liveness/readiness probe (a load
# balancer, Kubernetes, App Runner itself) needs one stable path across every
# version of the API, the same reason AWS's own health-check convention never
# asks for a version number. The business endpoints ARE versioned (/v1/rag/...)
# - a breaking change to the request/response shape later becomes /v2/rag/...
# without silently changing what /v1 callers already depend on.
app.include_router(routes_health.router)
app.include_router(routes_documents.router, prefix="/v1")
app.include_router(routes_query.router, prefix="/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch anything no route handler caught itself, so a client NEVER sees
    a raw stack trace or an internal exception message.

    Why this exists
    ----------------
    Every route handler is expected to catch its own known failure modes
    (see json_error() calls throughout api/) - this is the safety net for
    the ones that don't, or for a genuinely unexpected bug. Without it,
    FastAPI's own default handler returns Starlette's generic 500 page,
    which in debug contexts can include the full traceback - fine for a
    developer reading server logs, never fine in an HTTP response a caller
    might log, screenshot, or forward somewhere else.

    The split this enforces: the FULL exception (type, message, traceback)
    is always logged here, server-side, with the request path for context -
    that's where a developer actually diagnoses the bug. The CLIENT gets a
    generic message and nothing else. Matching a real Java equivalent: a
    global @ControllerAdvice/@ExceptionHandler in Spring that catches
    anything a specific @ExceptionHandler upstream didn't.
    """
    logger.error(
        "Unhandled exception on %s %s: %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
        exc_info=exc,
    )
    return json_error(500, "An internal error occurred. Please try again or contact support.")
