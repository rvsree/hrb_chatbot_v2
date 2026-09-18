from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common import error_codes
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.documents import (
    DocumentDeleteAllResponse,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentRecord,
    DocumentUploadResponse,
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
    # Upload, chunk, embed, and index one or more PDFs in one call (Phase
    # 26) - a single file is just a list of one.

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


@router.delete(
    "/documents", response_model=DocumentDeleteAllResponse, dependencies=[Depends(enforce_rate_limit)]
)
async def delete_all_documents():
    """Delete every document completely: vectors, metadata rows, uploaded
    files - same full delete as DELETE /documents/{id}, just for all of them."""
    result = await documents_service.delete_all_documents()
    return DocumentDeleteAllResponse(**result)
