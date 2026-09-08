"""The shared interface every vector database client implements.

Why this file exists
--------------------
ChromaDB, Pinecone and any future vector store all have different client
libraries with different method names and different call shapes. This class
defines the four operations the RAG pipeline actually needs, so calling code
can call `store.query(...)` without knowing or caring which backend is behind
it - the same reason BaseLLMClient exists for the LLM providers.

`ABC` means "Abstract Base Class". A class that inherits from it and does not
write all the `@abstractmethod` methods cannot be created - Python raises an
error straight away. That is what makes swapping the backend later safe: add
ChromaDBClient today, PineconeClient tomorrow, and forgetting a method on
either one fails immediately instead of at 2am in production.

What is deliberately NOT in this contract
------------------------------------------
`list_collections` and `delete_collection` are real operations ChromaDB
supports, but they are admin/maintenance actions, not something the RAG query
path or the indexing path needs on every call. Keeping them out of the
required contract keeps this interface small on purpose - add them back if a
concrete client actually needs to expose them.
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
        """Add or update chunks in one collection.

        `documents` is the chunk text itself (kept alongside the vector so a
        query result can return the original text, not just an id).
        `embeddings` must be the same length and order as `ids`/`documents`.
        """
        raise NotImplementedError

    @abstractmethod
    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Return the top_k chunks closest to query_embedding.

        `where` is an optional metadata filter (for example
        {"source_document": "healthcare_benefits.pdf"}) - every backend that
        implements this contract must support at least equality filtering on
        metadata fields, since the RAG pipeline's access-control and
        search-filter steps depend on it.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, collection_name: str, ids: list[str]) -> None:
        """Remove chunks by id - needed when a source document changes."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self, deep: bool = False) -> dict:
        """Report whether this client is usable.

        deep=False: only check that the connection settings are present. No
        network call.
        deep=True: make one real (but free/cheap) call to confirm the
        connection actually works - listing collections/indexes, not a query.
        """
        raise NotImplementedError
