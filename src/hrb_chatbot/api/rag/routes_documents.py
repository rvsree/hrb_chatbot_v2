"""Document upload and listing - free, no model call, no cost (except
POST .../index, which calls the real embedding model - see that
endpoint's own docstring).

Upload is deliberately decoupled from indexing (see docs/RAG-ROADMAP.md):
this router only stores files and records their metadata. A separate
POST /rag/documents/{id}/index endpoint - added alongside the chunking/
embedding/indexing work - is what actually processes a stored file. That
split means re-running indexing while developing chunking logic never
requires re-uploading.

Standardized here, across every endpoint that spends money or writes
state (see docs/FAQ.md's REST API contract-first section for the fuller
reasoning behind each):
- **Idempotency-Key support** - a client-supplied header; replaying the
  same key returns the cached response instead of re-running the request.
- **Rate limiting** - `Depends(enforce_rate_limit)`, off by default
  (APP_RATE_LIMITING in .env), per-client-IP when on.
- **A pre-flight config check before any real backend call** - fail with a
  clean 503 naming what's unconfigured, before spending anything, rather
  than letting a deep-in-the-pipeline exception surface as a raw 500.
- **No raw exception text in a client-facing response** - the full error
  is always logged server-side (see `logger.error(...)` calls below); the
  client gets a generic, safe message.
"""

from fastapi import APIRouter, Body, Depends, File, Header, UploadFile
from fastapi.responses import JSONResponse

from src.hrb_chatbot.ai.doc_processing import pipeline
from src.hrb_chatbot.api.admin.health_checks import check_llm, check_vector_database, is_working
from src.hrb_chatbot.api.dependencies import json_error
from src.hrb_chatbot.common.clients.db_client.db_gateway import get_db_gateway
from src.hrb_chatbot.common.idempotency.idempotency_store import get_idempotency_store
from src.hrb_chatbot.common.logging.logger import get_logger
from src.hrb_chatbot.common.rate_limiting.rate_limiter import enforce_rate_limit
from src.hrb_chatbot.models.documents import (
    DocumentListResponse,
    DocumentRecord,
    DocumentUploadResponse,
    IndexRequest,
    IndexResponse,
)
from src.hrb_chatbot.services import documents_service

logger = get_logger("routes_documents")

router = APIRouter(prefix="/rag", tags=["documents"])


@router.post("/documents", response_model=DocumentUploadResponse, dependencies=[Depends(enforce_rate_limit)])
async def upload_documents(
    files: list[UploadFile] = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Upload one or more PDF documents - a single file is just a list of one.

    Each file is validated and stored independently: one rejected file in a
    batch does not affect the others. Check each result's `status` rather
    than assuming the whole batch succeeded because the call returned 200.

    Pass an `Idempotency-Key` header to make a retry of this exact call
    safe - replaying the same key returns the same result instead of
    uploading the same file a second time under a new document_id.
    """
    store = get_idempotency_store()
    if idempotency_key:
        cached = store.get(idempotency_key)
        if cached is not None:
            status_code, body = cached
            return JSONResponse(status_code=status_code, content=body)

    results = await documents_service.save_uploads(files)

    # Count how many results have status "uploaded" - written as an explicit
    # loop rather than Python's sum(1 for ... if ...) idiom, which reads
    # naturally once you're used to it but is genuinely unfamiliar syntax
    # coming from Java (there's no direct equivalent to a generator
    # expression passed straight into a function call).
    uploaded_count = 0
    for result in results:
        if result.status == "uploaded":
            uploaded_count += 1
    rejected_count = len(results) - uploaded_count

    response = DocumentUploadResponse(
        uploaded_count=uploaded_count, rejected_count=rejected_count, results=results
    )

    if idempotency_key:
        store.set(idempotency_key, 200, response.model_dump())

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
        return json_error(404, f"Unknown document '{document_id}'")

    return DocumentRecord(**document)


def _preflight_backends_ready(vector_db: str | None) -> str | None:
    """Check (cheap, no network call - deep=False) that the embedding
    provider and the target vector store are at least configured, before
    attempting the real index operation.

    Returns a human-readable reason if something's missing, or None if
    it's safe to proceed. This deliberately does NOT make a deep (real
    network) call - that would just repeat the same cost the real
    operation is about to spend anyway, defeating the point of checking
    first. "Configured" only proves settings are present, not that the
    provider is actually reachable right now - the real call still catches
    that; this only catches the cheap, common mistake (a missing API key)
    before any money is spent trying.
    """
    llm_status = check_llm(deep=False)
    if not is_working(llm_status):
        return f"LLM provider is not configured: {llm_status.get('status')}"

    vector_status = check_vector_database(provider=vector_db or "chromadb", deep=False)
    if not is_working(vector_status):
        return f"Vector store is not configured: {vector_status.get('status')}"

    return None


@router.post(
    "/documents/{document_id}/index",
    response_model=IndexResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def index_document(
    document_id: str,
    payload: IndexRequest = Body(default=IndexRequest()),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Chunk, embed, and index one already-uploaded document.

    The body is entirely optional - every field defaults to this project's
    .env-configured default. Pass any subset of vector_db, chunk_size,
    chunk_overlap, embedding_model to override just that one setting for
    this call, without touching .env or affecting any other request.

    Safe to call more than once for the same document even without an
    Idempotency-Key: the second call is an update, not a duplicate - see
    ai/doc_processing/indexing/vector_indexer.py for how stale chunks from
    a previous index are removed rather than left behind. An
    Idempotency-Key is still worth sending anyway to avoid a real retry
    re-spending a real embedding call for no reason.
    """
    store = get_idempotency_store()
    if idempotency_key:
        cached = store.get(idempotency_key)
        if cached is not None:
            status_code, body = cached
            return JSONResponse(status_code=status_code, content=body)

    document = await documents_service.get_document(document_id)
    if document is None:
        return json_error(404, f"Unknown document '{document_id}'")

    preflight_failure_reason = _preflight_backends_ready(payload.vector_db)
    if preflight_failure_reason:
        logger.error(
            "Refusing to index document %s - preflight check failed: %s",
            document_id,
            preflight_failure_reason,
        )
        return json_error(503, "The indexing pipeline is not ready to accept requests right now.")

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
        # Full detail server-side only - see this file's own module
        # docstring for why the client never sees str(error) directly.
        logger.error("Indexing failed for document %s: %s: %s", document_id, type(error).__name__, error)
        await get_db_gateway().metadata_store().update_status(document_id, "failed", str(error))
        return json_error(500, "Indexing failed. Please try again.", document_id=document_id)

    await get_db_gateway().metadata_store().update_status(document_id, "indexed")
    response = IndexResponse(**result)

    if idempotency_key:
        store.set(idempotency_key, 200, response.model_dump())

    return response
