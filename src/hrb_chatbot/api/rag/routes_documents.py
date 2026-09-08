"""Document upload and listing - free, no model call, no cost.

Upload is deliberately decoupled from indexing (see docs/RAG-ROADMAP.md):
this router only stores files and records their metadata. A separate
POST /rag/documents/{id}/index endpoint - added alongside the chunking/
embedding/indexing work - is what actually processes a stored file. That
split means re-running indexing while developing chunking logic never
requires re-uploading.
"""

from fastapi import APIRouter, Body, File, UploadFile

from src.hrb_chatbot.ai.doc_processing import pipeline
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.models.documents import (
    DocumentListResponse,
    DocumentRecord,
    DocumentUploadResponse,
    IndexRequest,
    IndexResponse,
)
from src.hrb_chatbot.services import documents_service

router = APIRouter(prefix="/rag", tags=["documents"])


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)):
    """Upload one or more PDF documents - a single file is just a list of one.

    Each file is validated and stored independently: one rejected file in a
    batch does not affect the others. Check each result's `status` rather
    than assuming the whole batch succeeded because the call returned 200.
    """
    results = await documents_service.save_uploads(files)

    uploaded_count = sum(1 for result in results if result.status == "uploaded")
    rejected_count = len(results) - uploaded_count

    return DocumentUploadResponse(
        uploaded_count=uploaded_count, rejected_count=rejected_count, results=results
    )


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
        return json_error(404, f"Unknown document '{document_id}'")

    return DocumentRecord(**document)


@router.post("/documents/{document_id}/index", response_model=IndexResponse)
async def index_document(document_id: str, payload: IndexRequest = Body(default=IndexRequest())):
    """Chunk, embed, and index one already-uploaded document.

    The body is entirely optional - every field defaults to this project's
    .env-configured default. Pass any subset of vector_db, chunk_size,
    chunk_overlap, embedding_model to override just that one setting for
    this call, without touching .env or affecting any other request.

    Safe to call more than once for the same document: the second call is
    an update, not a duplicate - see ai/doc_processing/indexing/
    vector_indexer.py for how stale chunks from a previous index are
    removed rather than left behind.
    """
    document = await documents_service.get_document(document_id)
    if document is None:
        return json_error(404, f"Unknown document '{document_id}'")

    try:
        result = await pipeline.index_document(
            document_id,
            document["file_path"],
            vector_db=payload.vector_db,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
            embedding_model=payload.embedding_model,
        )
    except Exception as error:
        await get_db_gateway().metadata_store().update_status(document_id, "failed", str(error))
        return json_error(500, f"Indexing failed: {error}", document_id=document_id)

    await get_db_gateway().metadata_store().update_status(document_id, "indexed")
    return IndexResponse(**result)
