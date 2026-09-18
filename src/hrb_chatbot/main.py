from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

from src.hrb_chatbot.api.admin import routes_health
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.api.gateway.rbac import require_role
from src.hrb_chatbot.api.rag import routes_documents, routes_query
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title="HRB Chatbot",
    version="0.1.0",
    description="An HR benefits chatbot backed by a RAG pipeline over the JPMC benefits knowledge base.",
)

app.include_router(routes_health.router)
# Gateway role gate (Phase 23) - HR_SUPPORT only manages the knowledge base;
# all three roles can query it. See api/gateway/ for the (placeholder) identity source.
app.include_router(
    routes_documents.router,
    prefix="/v1/rag-ingestion",
    dependencies=[Depends(require_role(Role.HR_SUPPORT))]
)
app.include_router(
    routes_query.router,
    prefix="/v1/rag-retrieval",
    dependencies=[Depends(require_role(Role.EMPLOYEE, Role.MANAGER, Role.HR_SUPPORT))],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = jsonable_encoder(exc.errors(), custom_encoder={bytes: lambda value: value.decode("utf-8", errors="replace")})
    return json_error(422, "Request validation failed.", code=error_codes.VALIDATION_ERROR, details=details)


_ERROR_CODES_BY_STATUS = {
    401: error_codes.UNAUTHENTICATED,
    403: error_codes.FORBIDDEN,
    429: error_codes.RATE_LIMITED,
}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = _ERROR_CODES_BY_STATUS.get(exc.status_code, error_codes.INTERNAL_ERROR)
    return json_error(exc.status_code, str(exc.detail), code=code, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s: %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
        exc_info=exc,
    )
    return json_error(500, "An internal error occurred. Please try again or contact support.", code=error_codes.INTERNAL_ERROR)
