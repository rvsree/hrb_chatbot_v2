"""Ask the knowledge-base a question - spends real money on a well-formed
request (one embedding call, one chat completion, per query)."""

from fastapi import APIRouter, Request

from src.hrb_chatbot.ai.pre_processing.guardrails_input import GuardrailBlockedError
from src.hrb_chatbot.ai.rag_pipeline import pipeline
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.api.gateway.user_profile import resolve_user_from_profile
from src.hrb_chatbot.api.gateway.rbac import check_role
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.enums import Role
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rag_query_params import RagQueryParams
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.rag import AnswerInfo, RagQueryRequest, RagQueryResponse, RetrievalInfo

logger = get_logger("retrieve_document")

router_retrieve_document = APIRouter(tags=["query"])


def _params_from_request(payload: RagQueryRequest) -> RagQueryParams:
    """Map the nested request into the flat, framework-free dataclass every
    layer below the route actually uses - keeps ai/rag_pipeline/ unaware
    of this endpoint's wire shape."""
    search_options = payload.search_options
    generation_options = payload.generation_options
    return RagQueryParams(
        query=payload.query,
        top_k=search_options.top_k if search_options else None,
        vector_db=search_options.vector_db if search_options else None,
        search_strategy=search_options.search_strategy if search_options else None,
        model_name=generation_options.model_name if generation_options else None,
        temperature=generation_options.temperature if generation_options else None,
        max_tokens=generation_options.max_tokens if generation_options else None,
        use_multi_query=search_options.use_multi_query if search_options else False,
        use_self_query=search_options.use_self_query if search_options else False,
        llm_provider=search_options.llm_provider if search_options else None,
    )


async def _answer_query(payload: RagQueryRequest) -> RagQueryResponse | object:
    params = _params_from_request(payload)
    try:
        result = await pipeline.answer_query(params)
    except NotImplementedError as error:
        return json_error(501, str(error), code=error_codes.NOT_IMPLEMENTED)
    except GuardrailBlockedError as error:
        return json_error(422, str(error), code=error_codes.INPUT_GUARDRAIL_BLOCKED)
    except ValueError as error:
        return json_error(422, str(error), code=error_codes.VALIDATION_ERROR)
    except Exception as error:
        logger.error("Query failed for %r: %s: %s", payload.query, type(error).__name__, error)
        return json_error(
            500, "The query could not be answered. Please try again.", code=error_codes.QUERY_FAILED
        )

    return RagQueryResponse(
        query=result["query"],
        answer_info=AnswerInfo(answer=result["answer"], model_used=result["model_used"]),
        retrieval_info=RetrievalInfo(
            vector_db=result["vector_db"],
            search_strategy=result["search_strategy"],
            applied_filter=result.get("applied_filter"),
            sources=result["sources"],
        ),
    )


@router_retrieve_document.post("/query", response_model=RagQueryResponse)
async def query(payload: RagQueryRequest, request: Request):
    userProfile = resolve_user_from_profile(payload.user_profile)
    check_role(userProfile, Role.EMPLOYEE, Role.MANAGER, Role.HR_SUPPORT)
    enforce_rate_limit(request)
    return await _answer_query(payload)
