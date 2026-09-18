"""Ask the knowledge-base a question - spends real money on a well-formed
request (one embedding call, one chat completion, per query)."""

from fastapi import APIRouter, Depends

from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rag_query_params import RagQueryParams
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.rag import RagQueryRequest, RagQueryResponse
from src.hrb_chatbot.services import rag_service

logger = get_logger("routes_query")

router = APIRouter(tags=["query"])


async def _answer_query(payload: RagQueryRequest):
    # Ask a question and get back a grounded answer with its sources -
    # search_strategy comes from the request body, or defaults to 'similarity'.
    params = RagQueryParams(
        query=payload.query,
        top_k=payload.top_k,
        vector_db=payload.vector_db,
        search_strategy=payload.search_strategy,
        model_name=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        use_multi_query=payload.use_multi_query,
        use_self_query=payload.use_self_query,
        llm_provider=payload.llm_provider,
    )
    try:
        result = await rag_service.answer_query(params)
    except NotImplementedError as error:
        return json_error(501, str(error), code=error_codes.NOT_IMPLEMENTED)
    except ValueError as error:
        return json_error(422, str(error), code=error_codes.VALIDATION_ERROR)
    except Exception as error:
        logger.error("Query failed for %r: %s: %s", payload.query, type(error).__name__, error)
        return json_error(
            500, "The query could not be answered. Please try again.", code=error_codes.QUERY_FAILED
        )

    return RagQueryResponse(**result)


@router.post("/query", response_model=RagQueryResponse, dependencies=[Depends(enforce_rate_limit)])
async def query(payload: RagQueryRequest):
    # search_strategy comes from payload if given, or defaults to
    # 'similarity' - unchanged behavior from before this field existed.
    return await _answer_query(payload)
