"""Request/response contracts for the document upload API.

Why per-file results, not one status for the whole batch
-----------------------------------------------------------
A batch upload of 5 files where 1 is a .docx and 4 are valid PDFs should not
fail the 4 good ones because of the 1 bad one - the caller finds out exactly
which file failed and why, and the 4 that succeeded are already usable. See
services/documents_service.py for where that per-file validation happens.
"""

from pydantic import BaseModel, Field, model_validator

# A benefits PDF is a handful of pages, not a data dump - 20MB is generous
# headroom over anything in resources/kb_docs/ today, not an arbitrary number.
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_CONTENT_TYPE = "application/pdf"


class DocumentUploadResult(BaseModel):
    """What happened to one uploaded file."""

    filename: str = Field(..., description="The original filename as uploaded.")
    document_id: str | None = Field(
        None, description="The id assigned to this document, or null if it was rejected."
    )
    status: str = Field(..., description="'uploaded' if stored successfully, 'rejected' if not.")
    error: str | None = Field(None, description="Why this file was rejected, if it was.")


class DocumentUploadResponse(BaseModel):
    """What POST /rag/documents returns - one result per file, in upload order."""

    uploaded_count: int = Field(..., description="How many files were stored successfully.")
    rejected_count: int = Field(..., description="How many files were rejected.")
    results: list[DocumentUploadResult] = Field(..., description="One entry per file uploaded.")


class DocumentRecord(BaseModel):
    """One document's metadata, as returned by the list and get-by-id endpoints."""

    id: str
    filename: str
    file_path: str
    status: str = Field(..., description="'uploaded', 'indexed', or 'failed'.")
    error_message: str | None = None
    created_at: str
    updated_at: str
    chunk_ids: list[str] | None = Field(
        None,
        description=(
            "Vector-store ids this document's chunks were written under on its "
            "last successful index, or null if it has never been indexed."
        ),
    )


class DocumentListResponse(BaseModel):
    """What GET /rag/documents returns."""

    count: int
    documents: list[DocumentRecord]


class IndexRequest(BaseModel):
    """Optional per-call overrides for POST /rag/documents/{id}/index.

    Every field defaults to the .env-configured default when omitted (or
    when the whole body is omitted) - this request only needs to carry the
    values that differ from that default for this one call.
    """

    vector_db: str | None = Field(
        None, max_length=50, description="Override RAG_VECTOR_DB for this call: 'chromadb' or 'pinecone'."
    )
    chunk_size: int | None = Field(
        None, ge=100, le=8000, description="Override the default chunk size, in characters."
    )
    chunk_overlap: int | None = Field(
        None,
        ge=0,
        le=8000,
        description=(
            "Override the default chunk overlap, in characters. The upper bound matches "
            "chunk_size's own maximum - an overlap larger than any allowed chunk_size can never "
            "be valid, so it's rejected here directly rather than only by the "
            "chunk_overlap-must-be-smaller-than-chunk_size check below, which only runs when "
            "both fields are given together."
        ),
    )
    embedding_model: str | None = Field(
        None,
        max_length=100,
        description=(
            "Override OPENAI_EMBED_MODEL for this call, e.g. 'text-embedding-3-large'. "
            "Must produce the same dimension the target vector store's index was "
            "created with, or the upsert fails - this is not cross-checked."
        ),
    )

    @model_validator(mode="after")
    def _chunk_overlap_must_be_smaller_than_chunk_size(self) -> "IndexRequest":
        if self.chunk_size is not None and self.chunk_overlap is not None:
            if self.chunk_overlap >= self.chunk_size:
                raise ValueError(
                    f"chunk_overlap ({self.chunk_overlap}) must be smaller than "
                    f"chunk_size ({self.chunk_size})"
                )
        return self


class IndexResponse(BaseModel):
    """What POST /rag/documents/{id}/index returns."""

    document_id: str
    action: str = Field(
        ..., description="'insert' if this document had never been indexed, 'update' if it had."
    )
    chunks_indexed: int = Field(..., description="How many chunks were written this time.")
    chunks_removed: int = Field(
        ...,
        description=(
            "Stale chunks from a previous index that no longer exist in the new "
            "set, and were deleted rather than left orphaned. Always 0 on 'insert'."
        ),
    )
    vector_db: str = Field(..., description="Which vector store this call actually wrote to.")
    embedding_model: str = Field(..., description="Which embedding model this call actually used.")
    chunk_size: int = Field(..., description="The chunk size actually used for this call.")
    chunk_overlap: int = Field(..., description="The chunk overlap actually used for this call.")
