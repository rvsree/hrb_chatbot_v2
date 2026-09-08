"""The shared interface every document-metadata store implements.

Why this exists
----------------
The vector store (ChromaDB/Pinecone) holds chunks and embeddings. Something
separate has to hold one row per *uploaded document* - its filename, where
its raw bytes live on disk, and whether it's been indexed yet - so
`GET /rag/documents/{id}` can answer "what happened to this file" without
asking the vector store, which doesn't know what a "document" is, only what
a "chunk" is.

Same pattern as BaseVectorDBClient
-----------------------------------
SQLite is the active implementation; Postgres is a fully working, tested
alternative behind the same contract, same relationship as PineconeClient
to ChromaDBClient.

Why chunk_ids is tracked here, not just in the vector store
------------------------------------------------------------
Re-indexing a document has to know which chunks it produced *last time*, so
the old ones can be deleted before the new ones are written - otherwise, if
a document shrinks (produces fewer chunks on a re-index than it did
before), the extra old chunks are orphaned in the vector store forever,
pointing at content that's no longer considered current. The vector store
itself has no concept of "all the chunks belonging to one document" to ask
for later, so that list is kept here instead, next to the rest of the
document's metadata.
"""

from abc import ABC, abstractmethod


class BaseMetadataClient(ABC):
    """Every document-metadata store (SQLite, Postgres, ...) inherits from this."""

    PROVIDER_NAME = "base"
    ENV_KEY = ""

    @abstractmethod
    async def create_document(self, document_id: str, filename: str, file_path: str) -> None:
        """Insert one row for a newly-uploaded document, status 'uploaded'."""
        raise NotImplementedError

    @abstractmethod
    async def update_status(
        self, document_id: str, status: str, error_message: str | None = None
    ) -> None:
        """Move a document to 'indexed' or 'failed', recording why if it failed."""
        raise NotImplementedError

    @abstractmethod
    async def set_chunk_ids(self, document_id: str, chunk_ids: list[str]) -> None:
        """Record which vector-store ids this document's chunks were written
        under, replacing whatever was recorded on a previous index. Read
        back via get_document(...)["chunk_ids"] (a JSON-encoded list, or
        None if the document has never been indexed)."""
        raise NotImplementedError

    @abstractmethod
    async def get_document(self, document_id: str) -> dict | None:
        """Return one document's row, or None if the id doesn't exist."""
        raise NotImplementedError

    @abstractmethod
    async def list_documents(self) -> list[dict]:
        """Return every document row, newest first."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self, deep: bool = False) -> dict:
        """Report whether this store is usable - never raises, same contract
        as every other client's health_check in this project."""
        raise NotImplementedError
