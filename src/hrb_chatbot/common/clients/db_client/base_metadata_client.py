"""Shared interface every document-metadata store implements - one row per
document; chunk_ids tracked here so re-indexing can find stale chunks to delete."""

from abc import ABC, abstractmethod


class BaseMetadataClient(ABC):
    """Every document-metadata store (SQLite, Postgres, ...) inherits from this."""

    PROVIDER_NAME = "base"
    ENV_KEY = ""

    @abstractmethod
    async def create_document(
        self,
        document_id: str,
        filename: str,
        file_path: str,
        file_size_bytes: int,
        content_hash: str,
        supersedes: str | None = None,
    ) -> None:
        """Insert one row for a newly-uploaded document (status 'uploaded',
        version 1, is_current true). `supersedes` only records intent here -
        the actual flip happens later, in record_successful_index()."""
        raise NotImplementedError

    @abstractmethod
    async def find_by_content_hash(self, content_hash: str) -> dict | None:
        """Return the most recent document with this exact content hash, or
        None - same bytes/any filename means "same document," not a fresh one."""
        raise NotImplementedError

    @abstractmethod
    async def update_status(
        self, document_id: str, status: str, error_message: str | None = None
    ) -> None:
        """Move a document to 'indexed' or 'failed', recording why if it failed."""
        raise NotImplementedError

    @abstractmethod
    async def set_chunk_ids(self, document_id: str, chunk_ids: list[str]) -> None:
        """Record which vector-store ids this document's chunks were written under,
        replacing the previous record. Read back via get_document()["chunk_ids"]."""
        raise NotImplementedError

    @abstractmethod
    async def record_successful_index(
        self,
        document_id: str,
        chunk_ids: list[str],
        embedding_model: str,
        embedding_dimension: int,
        vector_db: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> int:
        """One update for everything a successful index changes: chunk_ids,
        counts, model/store/chunk settings, status -> 'indexed', version += 1
        - plus the `chunks` table (delete-then-insert). Returns the new version."""
        raise NotImplementedError

    @abstractmethod
    async def mark_superseded(self, document_id: str, superseded_by: str) -> list[str]:
        """Flip an existing document to is_current=false (its row + `chunks`
        rows), recording its replacement. Returns chunk_ids so the caller can
        also flip the vector store - this method only ever touches SQL."""
        raise NotImplementedError

    @abstractmethod
    async def record_document_metadata(
        self,
        document_id: str,
        owner: str | None,
        department: str | None,
        doc_type: str | None,
        purpose: str | None,
        doc_classification: str | None,
    ) -> None:
        """Record LLM-extracted document metadata (best-effort - any field may
        be None if extraction couldn't determine it). Never raises; a failure
        to extract this enrichment must not block indexing itself."""
        raise NotImplementedError

    @abstractmethod
    async def get_document(self, document_id: str) -> dict | None:
        """Return one document's row, or None if the id doesn't exist."""
        raise NotImplementedError

    @abstractmethod
    async def delete_document(self, document_id: str) -> None:
        """Remove one document's row - a no-op if the id doesn't exist (the
        404 check is documents_service.delete_document()'s job, not this one's)."""
        raise NotImplementedError

    @abstractmethod
    async def list_documents(self) -> list[dict]:
        """Return every document row, newest first."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict:
        """Report whether this store is usable - never raises, same contract
        as every other client's health_check in this project."""
        raise NotImplementedError
