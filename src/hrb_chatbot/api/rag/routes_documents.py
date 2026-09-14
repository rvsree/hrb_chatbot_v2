from fastapi import APIRouter, Body, Depends, File, Form, UploadFile

from src.hrb_chatbot.ai.doc_processing import pipeline
from src.hrb_chatbot.ai.doc_processing.chunking.text_chunker import CHUNKING_STRATEGIES
from src.hrb_chatbot.api.admin.health_checks import check_llm, check_vector_database, is_working
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.enums import VectorDB
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.documents import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentRecord,
    DocumentUploadResponse,
    IndexRequest,
    IndexResponse,
)
from src.hrb_chatbot.services import documents_service

logger = get_logger("routes_documents")

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=DocumentUploadResponse, dependencies=[Depends(enforce_rate_limit)])
async def upload_documents(
    files: list[UploadFile] = File(...),
    supersedes_document_id: str | None = Form(
        default=None,
        description="Explicitly marks this upload as a new version of an existing document. Only valid "
        "with exactly one file - the old document is flipped to is_current=false once this one "
        "successfully indexes, not immediately on upload.",
    ),
):
    # Upload one or more PDF documents - a single file is just a list of one.

    if supersedes_document_id and len(files) != 1:
        return json_error(
            422,
            "supersedes_document_id is only valid with exactly one file - ambiguous for a batch upload.",
            code=error_codes.VALIDATION_ERROR,
        )

    results = await documents_service.save_uploads(files, supersedes_document_id=supersedes_document_id)

    uploaded_count = 0
    duplicate_count = 0
    for result in results:
        if result.status == "uploaded":
            uploaded_count += 1
        elif result.status == "duplicate":
            duplicate_count += 1
    rejected_count = len(results) - uploaded_count - duplicate_count

    response = DocumentUploadResponse(
        uploaded_count=uploaded_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
        results=results,
    )

    return response


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """List every uploaded document and its current status."""
    documents = await documents_service.list_documents()
    return DocumentListResponse(count=len(documents), documents=documents)


@router.get("/documents/{document_id}", response_model=DocumentRecord)
async def get_document(document_id: str):
    """Get one document's metadata by id."""
    document = await documents_service.get_document(document_id)

    if document is None:
        return json_error(404, f"Unknown document '{document_id}'", code=error_codes.DOCUMENT_NOT_FOUND)

    return DocumentRecord(**document)


@router.delete(
    "/documents/{document_id}", response_model=DocumentDeleteResponse, dependencies=[Depends(enforce_rate_limit)]
)
async def delete_document(document_id: str):
    """Delete one document completely: its vectors, its metadata row, and its
    uploaded file. A full delete, not selective - see DocumentDeleteResponse's
    docstring for why "delete one version, keep another" doesn't apply here."""
    result = await documents_service.delete_document(document_id)

    if result is None:
        return json_error(404, f"Unknown document '{document_id}'", code=error_codes.DOCUMENT_NOT_FOUND)

    return DocumentDeleteResponse(**result)


def _preflight_backends_ready(vector_db: VectorDB | None) -> str | None:
    # Check the embedding LLM and the vector store are actually reachable before
    # spending time parsing and chunking the PDF - see check_llm/check_vector_database,
    # the same real (never raises, one free call) checks GET /health itself uses.
    llm_status = check_llm()
    if not is_working(llm_status):
        return f"LLM provider is not available: {llm_status.get('message', llm_status.get('status'))}"

    vector_status = check_vector_database(provider=vector_db or VectorDB.CHROMADB)
    if not is_working(vector_status):
        return f"Vector store is not available: {vector_status.get('message', vector_status.get('status'))}"

    return None


async def _index_document(document_id: str, payload: IndexRequest):
    # Chunk, embed, and index one already-uploaded document. Shared by both the dynamic endpoint
    # (chunking_strategy from the request body, or auto-selected if omitted) and the per-strategy endpoints below
    # (chunking_strategy fixed from the URL path).
    document = await documents_service.get_document(document_id)
    if document is None:
        return json_error(404, f"Unknown document '{document_id}'", code=error_codes.DOCUMENT_NOT_FOUND)

    preflight_failure_reason = _preflight_backends_ready(payload.vector_db)
    if preflight_failure_reason:
        logger.error("Document indexing failed %s - preflight check failed: %s", document_id, preflight_failure_reason)
        # preflight_failure_reason comes from health_check(), which never raises and
        # never includes a raw exception/stack trace (see CODING-STANDARDS.md) - safe
        # to hand back to the caller as-is, unlike the generic except Exception below.
        return json_error(503, preflight_failure_reason, code=error_codes.BACKEND_UNAVAILABLE)

    try:
        result = await pipeline.index_document(
            document_id,
            document["file_path"],
            vector_db=payload.vector_db,
            chunking_strategy=payload.chunking_strategy,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
            embedding_model=payload.embedding_model,
        )
    except ValueError as error:
        return json_error(422, str(error), code=error_codes.VALIDATION_ERROR)
    except Exception as error:
        # Full detail server-side only - see this file's own module
        # docstring for why the client never sees str(error) directly.
        logger.error("Indexing failed for document %s: %s: %s", document_id, type(error).__name__, error)
        await get_db_gateway().metadata_store().update_status(document_id, "failed", str(error))
        return json_error(
            500, "Indexing failed. Please try again.", code=error_codes.INDEXING_FAILED, document_id=document_id
        )

    # status -> "indexed" already happened inside pipeline.index_document() ->
    # write_chunks() -> record_successful_index() - one write for the whole
    # successful outcome, not a separate status update here too.
    return IndexResponse(**result)


@router.post(
    "/documents/{document_id}/index",
    response_model=IndexResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def index_document(
    document_id: str,
    payload: IndexRequest = Body(default=IndexRequest()),
):
    # chunking_strategy comes from payload if given, or is auto-selected -
    # see text_chunker.decide_chunking_strategy().
    return await _index_document(document_id, payload)


@router.post(
    "/documents/{document_id}/index/{chunking_strategy}",
    response_model=IndexResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def index_document_with_strategy(
    document_id: str,
    chunking_strategy: str,
    payload: IndexRequest = Body(default=IndexRequest()),
):
    # One dedicated URL per chunking technique, e.g. .../index/recursive,
    # .../index/semantic - same underlying pipeline as the dynamic endpoint
    # above, just with chunking_strategy fixed from the URL instead of the
    # request body (any chunking_strategy in the body is ignored here).
    if chunking_strategy not in CHUNKING_STRATEGIES:
        return json_error(
            404,
            f"Unknown chunking strategy {chunking_strategy!r} - choose one of {list(CHUNKING_STRATEGIES)}",
            code=error_codes.VALIDATION_ERROR,
        )

    payload = payload.model_copy(update={"chunking_strategy": chunking_strategy})
    return await _index_document(document_id, payload)
