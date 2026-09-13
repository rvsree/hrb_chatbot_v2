"""The shared interface every vector database client implements.

ChromaDB, Pinecone, etc. have different client libraries; this defines the
four operations the RAG pipeline needs so calling code can use any backend
interchangeably. Admin-only operations like list_collections/delete_collection
are deliberately left out to keep the required contract small.
"""

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
        """Return the top_k chunks closest to query_embedding. `where` is an optional
        metadata filter; every backend must support at least equality filtering on it,
        since the RAG pipeline's access-control and search-filter steps depend on it."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, collection_name: str, ids: list[str]) -> None:
        """Remove chunks by id - needed when a source document changes."""
        raise NotImplementedError

    @abstractmethod
    def update_metadata(self, collection_name: str, ids: list[str], metadatas: list[dict]) -> None:
        """Update only the metadata on existing chunks, without re-supplying
        embeddings/documents - used to flip is_current=false on a superseded
        document's chunks without a wasted re-embed. `metadatas[i]` REPLACES
        the full metadata dict for `ids[i]`, not a merge - callers must pass
        every field they want kept, not just the ones changing."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable. deep=False only checks that
        connection settings are present; deep=True makes one cheap real call (listing collections/indexes)."""
        raise NotImplementedError
