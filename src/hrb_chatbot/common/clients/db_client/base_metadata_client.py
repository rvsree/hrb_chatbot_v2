"""The shared interface every document-metadata store implements.

Holds one row per uploaded document (filename, path, status) - separate from
the vector store, which only knows about chunks. chunk_ids is tracked here,
not in the vector store, so re-indexing can delete a document's stale chunks
before writing new ones; the vector store has no concept of "all chunks
belonging to one document" to ask for later.
"""

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
        """Insert one row for a newly-uploaded document: status 'uploaded',
        document_version 1, is_current true. `supersedes` records - at upload
        time, before this document is even indexed - that it's intended to
        replace an existing document once it successfully indexes; the actual
        supersede (flipping the old document to is_current=false) happens in
        record_successful_index(), not here, so there's never a window where
        neither version's content is live."""
        raise NotImplementedError

    @abstractmethod
    async def find_by_content_hash(self, content_hash: str) -> dict | None:
        """Return the most recent document with this exact content hash, or None if
        no upload has ever had this content before. The dedup check - same bytes,
        any filename, means "this is the same document," not a fresh one."""
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
        """One update for everything a successful index run changes: chunk_ids,
        chunk_count, which embedding model/vector store/chunk settings produced
        them, status -> 'indexed', error_message cleared, and document_version
        incremented by one. Also replaces this document's rows in the `chunks`
        table (delete-then-insert, matching the vector store's own stale-chunk
        cleanup). Returns the new document_version."""
        raise NotImplementedError

    @abstractmethod
    async def mark_superseded(self, document_id: str, superseded_by: str) -> list[str]:
        """Flip an existing document to is_current=false (both its own row and
        its rows in `chunks`), recording which new document replaced it.
        Returns its chunk_ids (if any) so the caller can also flip the
        matching vectors' is_current metadata in the vector store - this
        method only ever touches SQL, never the vector store directly.
        Called once the *new* document has successfully indexed, never at
        upload time - see create_document()'s `supersedes` param for why."""
        raise NotImplementedError

    @abstractmethod
    async def record_document_metadata(
        self,
        document_id: str,
        owner: str | None,
        department: str | None,
        doc_type: str | None,
        purpose: str | None,
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
        """Remove one document's row. A no-op, not an error, if the id doesn't
        exist - the caller (documents_service.delete_document()) is responsible
        for the 404 check before this is ever called."""
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
