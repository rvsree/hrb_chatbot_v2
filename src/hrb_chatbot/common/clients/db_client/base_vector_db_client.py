"""Shared interface every vector database client implements - ChromaDB,
Pinecone, etc. behind four backend-agnostic operations."""

from abc import ABC, abstractmethod


class BaseVectorDBClient(ABC):
    """Every vector store client (ChromaDB, Pinecone, ...) inherits from this."""

    # Each subclass overrides these two with its own values.
    PROVIDER_NAME = "base"
    ENV_KEY = ""

    @abstractmethod
    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add or update chunks in one collection. `documents` is the chunk text
        (kept so a query result can return it, not just an id); `embeddings` must align by index with `ids`."""
        raise NotImplementedError

    @abstractmethod
    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Return the top_k chunks closest to query_embedding. `where` is an
        optional metadata filter every backend must support (at least equality)."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, collection_name: str, ids: list[str]) -> None:
        """Remove chunks by id - needed when a source document changes."""
        raise NotImplementedError

    @abstractmethod
    def update_metadata(self, collection_name: str, ids: list[str], metadatas: list[dict]) -> None:
        """Update only metadata on existing chunks, no re-embed. `metadatas[i]`
        REPLACES the full dict for `ids[i]`, not a merge - pass every field
        to keep, not just the ones changing."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict:
        """Report whether this client is usable: makes one cheap real call
        (listing collections/indexes) and reports the outcome - never raises."""
        raise NotImplementedError
