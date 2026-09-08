"""Shared test fixtures - the fakes every test file below imports instead of
each writing its own.

Why fakes, not real backends
-----------------------------
No test in this suite may reach a real network, cost money, or need an API
key - the same rule the reference project (w1_agentic_foundations) already
follows, and the same reason for it here: a test that calls the real
OpenAI API is flaky (network, rate limits), slow, and either needs a key
in CI or gets silently skipped there. A fake with the exact same method
signatures as the real client (FakeEmbeddingClient looks like
OpenAIEmbeddingClient to any code that calls it) tests the same logic
without any of that.

Why "monkeypatch", for anyone coming from Java
-------------------------------------------------
pytest's `monkeypatch` fixture temporarily replaces one function/attribute
for the duration of a single test, then puts the original back
automatically when the test ends - closest Java analogue is a mocking
framework like Mockito swapping in a mock for the scope of one test method,
except monkeypatch works directly on Python's module-level names rather
than needing an interface to mock against.
"""

from src.hrb_chatbot.common.clients.db_client.base_metadata_client import BaseMetadataClient
from src.hrb_chatbot.common.clients.db_client.base_vector_db_client import BaseVectorDBClient


class FakeEmbeddingClient:
    """Stands in for OpenAIEmbeddingClient - no network, a fixed-size vector
    per text, and a record of every call so a test can assert on what was
    actually asked for (which model, how many texts)."""

    def __init__(self, dimension: int = 4):
        self.dimension = dimension
        self.calls: list[dict] = []

    def get_embeddings(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        self.calls.append({"texts": texts, "model": model})
        embeddings = []
        for _ in texts:
            embeddings.append([0.1] * self.dimension)
        return embeddings


class FakeClientGateway:
    """Stands in for ClientGateway - just enough to return a FakeEmbeddingClient
    where real code calls get_client_gateway().openai_embedding()."""

    def __init__(self, embedding_client: FakeEmbeddingClient | None = None):
        self._embedding_client = embedding_client or FakeEmbeddingClient()

    def openai_embedding(self) -> FakeEmbeddingClient:
        return self._embedding_client


class FakeVectorStore(BaseVectorDBClient):
    """An in-memory vector store - a plain dict keyed by chunk id, standing in
    for ChromaDBClient/PineconeClient. Real enough to prove insert/update/
    delete logic works, with none of ChromaDB's or Pinecone's own setup."""

    PROVIDER_NAME = "fake"

    def __init__(self):
        # {collection_name: {chunk_id: {"document": ..., "embedding": ..., "metadata": ...}}}
        self.collections: dict[str, dict[str, dict]] = {}
        self.upsert_calls: list[dict] = []
        self.delete_calls: list[dict] = []

    def upsert(self, collection_name, ids, documents, embeddings, metadatas=None):
        self.upsert_calls.append({"collection_name": collection_name, "ids": list(ids)})
        if collection_name not in self.collections:
            self.collections[collection_name] = {}
        collection = self.collections[collection_name]

        if metadatas is None:
            metadatas = []
            for _ in ids:
                metadatas.append({})

        for chunk_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas, strict=True):
            collection[chunk_id] = {"document": document, "embedding": embedding, "metadata": metadata}

    def query(self, collection_name, query_embedding, top_k=5, where=None):
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def delete(self, collection_name, ids):
        self.delete_calls.append({"collection_name": collection_name, "ids": list(ids)})
        collection = self.collections.get(collection_name, {})
        for chunk_id in ids:
            collection.pop(chunk_id, None)

    def health_check(self, deep=False):
        return {"provider": self.PROVIDER_NAME, "status": "healthy"}


class FakeMetadataStore(BaseMetadataClient):
    """An in-memory metadata store - standing in for SQLiteClient/PostgresClient.
    Documents are kept in a plain dict, keyed by document_id."""

    PROVIDER_NAME = "fake"

    def __init__(self):
        self.documents: dict[str, dict] = {}

    async def create_document(self, document_id, filename, file_path):
        self.documents[document_id] = {
            "id": document_id,
            "filename": filename,
            "file_path": file_path,
            "status": "uploaded",
            "error_message": None,
            "chunk_ids": None,
        }

    async def update_status(self, document_id, status, error_message=None):
        if document_id in self.documents:
            self.documents[document_id]["status"] = status
            self.documents[document_id]["error_message"] = error_message

    async def set_chunk_ids(self, document_id, chunk_ids):
        import json

        if document_id in self.documents:
            self.documents[document_id]["chunk_ids"] = json.dumps(chunk_ids)

    async def get_document(self, document_id):
        return self.documents.get(document_id)

    async def list_documents(self):
        return list(self.documents.values())

    def health_check(self, deep=False):
        return {"provider": self.PROVIDER_NAME, "status": "healthy"}


class FakeDBGateway:
    """Stands in for DBGateway - returns the one FakeVectorStore/FakeMetadataStore
    given to it, regardless of which provider name is asked for. A test that
    needs to tell two different providers apart should use two FakeDBGateway
    instances, not rely on this one to fake that distinction."""

    def __init__(self, vector_store: FakeVectorStore | None = None, metadata_store: FakeMetadataStore | None = None):
        self._vector_store = vector_store or FakeVectorStore()
        self._metadata_store = metadata_store or FakeMetadataStore()

    def vector_store(self, provider=None):
        return self._vector_store

    def metadata_store(self, provider=None):
        return self._metadata_store
