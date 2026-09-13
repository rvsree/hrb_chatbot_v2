"""Ask the knowledge-base a question - spends real money on a well-formed
request (one embedding call, one chat completion, per query)."""

from fastapi import APIRouter, Depends

from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.rag import RagQueryRequest, RagQueryResponse
from src.hrb_chatbot.services import rag_service

logger = get_logger("routes_query")

router = APIRouter(tags=["query"])


@router.post("/query", response_model=RagQueryResponse, dependencies=[Depends(enforce_rate_limit)])
async def query(payload: RagQueryRequest):
    # Ask a question and get back a grounded answer with its sources.
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
        return json_error(501, str(error), code=error_codes.NOT_IMPLEMENTED)
    except Exception as error:
        logger.error("Query failed for %r: %s: %s", payload.query, type(error).__name__, error)
        return json_error(
            500, "The query could not be answered. Please try again.", code=error_codes.QUERY_FAILED
        )

    return RagQueryResponse(**result)
