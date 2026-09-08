"""Ask the knowledge base a question - free to call, but the underlying
pipeline spends real money once Phase 6 replaces its stub (an embedding
call and a chat completion per query).

The pipeline itself (ai/rag_pipeline/pipeline.py) is hand-written and not
implemented yet - this endpoint's job is only to validate the request, call
the entry point, and turn whatever happens into a clear response. 501 here
means "not built yet", not "broken" - same convention as the indexing
endpoint before it was implemented.
"""

from fastapi import APIRouter

from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.models.rag import RagQueryRequest, RagQueryResponse
from src.hrb_chatbot.services import rag_service

router = APIRouter(prefix="/rag", tags=["query"])


@router.post("/query", response_model=RagQueryResponse)
async def query(payload: RagQueryRequest):
    """Ask a question and get back a grounded answer with its sources."""
    try:
        result = await rag_service.answer_query(
            payload.query, top_k=payload.top_k, vector_db=payload.vector_db
        )
    except NotImplementedError as error:
        return json_error(501, str(error))
    except Exception as error:
        return json_error(500, f"Query failed: {error}")

    return RagQueryResponse(**result)
