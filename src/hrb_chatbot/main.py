from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

from src.hrb_chatbot.api.admin import routes_health
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.api.rag import routes_documents, routes_query
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title="HRB Chatbot",
    version="0.1.0",
    description="An HR benefits chatbot backed by a RAG pipeline over the JPMC benefits knowledge base.",
)

app.include_router(routes_health.router)
app.include_router(routes_documents.router, prefix="/v1/rag-ingestion")
app.include_router(routes_query.router, prefix="/v1/rag-retrieval")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # exc.errors() can contain a raw ValueError object (in "ctx") when a Pydantic
    # @model_validator raises one - e.g. IndexRequest's chunk_overlap/chunk_size
    # check - and json.dumps() crashes on that. jsonable_encoder() converts it to
    # something JSON-safe; the human-readable text is already in "msg" either way.
    return json_error(
        422, "Request validation failed.", code=error_codes.VALIDATION_ERROR, details=jsonable_encoder(exc.errors())
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = error_codes.RATE_LIMITED if exc.status_code == 429 else error_codes.INTERNAL_ERROR
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
