"""Request/response contracts for the document upload API.

Per-file results, not one status for the whole batch: one bad file in a
batch shouldn't fail the good ones - each gets its own status and reason.
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
        None,
        description=(
            "The id this document is stored under, or null if it was rejected. On a 'duplicate' "
            "result, this is the EXISTING document's id, not a new one."
        ),
    )
    status: str = Field(
        ...,
        description=(
            "'uploaded' if a new document was stored, 'duplicate' if identical content was already "
            "uploaded before (no new document created - see message), 'rejected' if invalid."
        ),
    )
    error: str | None = Field(None, description="Why this file was rejected, if it was.")
    error_code: str | None = Field(
        None,
        description=(
            "Stable, machine-readable reason for a 'rejected' result (see common/error_codes.py) - "
            "e.g. INVALID_FILE_TYPE, EMPTY_FILE, FILE_TOO_LARGE - for a caller deciding which files "
            "in a batch are worth retrying, without string-matching `error`'s prose."
        ),
    )
    message: str | None = Field(
        None, description="Informational note, e.g. which existing document a 'duplicate' matched."
    )
    file_size_bytes: int | None = Field(
        None, description="The file's size in bytes - present for 'uploaded' and 'duplicate', null "
        "for 'rejected'."
    )
    document_version: int | None = Field(
        None, description="1 on a fresh upload, or the existing document's current version on a "
        "'duplicate' match - null if rejected. Increments on each successful (re-)index, see "
        "DocumentRecord.document_version."
    )


class DocumentUploadResponse(BaseModel):
    """What POST /rag/documents returns - one result per file, in upload order."""

    uploaded_count: int = Field(..., description="How many files were stored as new documents.")
    duplicate_count: int = Field(
        ..., description="How many files matched a document already uploaded - see each result's "
        "message for which existing document_id."
    )
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
    document_version: int = Field(
        1, description="Starts at 1 on upload, increments by 1 on each successful (re-)index."
    )
    file_size_bytes: int = Field(0, description="The uploaded file's size in bytes.")
    chunk_count: int = Field(
        0, description="How many chunks this document currently has - len(chunk_ids), kept as its "
        "own column so a list view doesn't need to parse the full chunk_ids array just to count."
    )
    embedding_model: str | None = Field(
        None, description="Which embedding model produced the current chunks, or null if never indexed."
    )
    embedding_dimension: int | None = Field(
        None,
        description=(
            "The vector length that model produced (e.g. 1536 for text-embedding-3-small, 3072 for "
            "text-embedding-3-large) - the actual length of a real embedding this document's chunks "
            "were written with, not looked up from a hardcoded model name table. Mixing dimensions "
            "within one vector-store collection breaks it, so this is what to check before reusing "
            "a vector_db override across documents."
        ),
    )
    vector_db: str | None = Field(
        None, description="Which vector store this document's chunks currently live in, or null if "
        "never indexed."
    )
    chunk_size: int | None = Field(None, description="The chunk size used for the current index.")
    chunk_overlap: int | None = Field(None, description="The chunk overlap used for the current index.")
    last_indexed_at: str | None = Field(
        None,
        description=(
            "When the most recent *successful* index finished - unlike updated_at, this doesn't "
            "move on a failed index attempt, so it always answers \"how fresh is what's actually "
            "searchable for this document\"."
        ),
    )
    is_current: bool = Field(
        True,
        description=(
            "False once a newer upload has explicitly superseded this document (see supersedes/"
            "superseded_by) - its chunks are excluded from retrieval by default, though not deleted."
        ),
    )
    supersedes: str | None = Field(
        None, description="The document_id this one explicitly replaced, if any - set at upload time."
    )
    superseded_by: str | None = Field(
        None, description="The document_id that replaced this one, if any - set once that document "
        "successfully indexes, not immediately when it's uploaded."
    )
    owner: str | None = Field(
        None, description="Who owns this document, if the LLM extraction step could determine it - "
        "null if never indexed, or if extraction couldn't tell."
    )
    department: str | None = Field(None, description="Which department this document belongs to, if determinable.")
    doc_type: str | None = Field(
        None, description="e.g. 'policy', 'regulatory', 'investment' - the extraction step's best guess, "
        "not a controlled vocabulary."
    )
    purpose: str | None = Field(None, description="A short statement of the document's scope/purpose, if determinable.")


class DocumentListResponse(BaseModel):
    """What GET /rag/documents returns."""

    count: int
    documents: list[DocumentRecord]


class DocumentDeleteResponse(BaseModel):
    """What DELETE /rag/documents/{id} returns - a full delete: vectors, the
    metadata row, and the uploaded file, all removed. Not partial/selective -
    a document has one current version, not a retained history to pick from."""

    document_id: str
    filename: str = Field(..., description="The deleted document's filename, for confirmation.")
    chunks_removed: int = Field(
        ..., description="How many vectors were deleted from the vector store. 0 if the document "
        "had never been indexed."
    )


class IndexRequest(BaseModel):
    # Optional per-call overrides for POST /rag/documents/{id}/index.

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
    embedding_dimension: int = Field(
        ..., description="The real length of the embeddings this call produced - see "
        "DocumentRecord.embedding_dimension for why this is measured, not looked up."
    )
    chunk_size: int = Field(..., description="The chunk size actually used for this call.")
    chunk_overlap: int = Field(..., description="The chunk overlap actually used for this call.")
    document_version: int = Field(
        ..., description="This document's version after this call - increments by 1 on every "
        "successful index, starting from 1 on upload."
    )
