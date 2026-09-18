"""Shared test fixtures - fakes every test file below imports instead of
writing its own. No test may hit a real network, cost money, or need an
API key, so these fakes match the real clients' method signatures exactly.
`monkeypatch` (pytest) swaps a function/attribute for one test, then
restores it automatically - like Mockito, but on Python's module names."""

from langchain_core.embeddings import Embeddings

from src.hrb_chatbot.common.clients.db_client.base_metadata_client import BaseMetadataClient
from src.hrb_chatbot.common.clients.db_client.base_vector_db_client import BaseVectorDBClient


class FakeEmbeddings(Embeddings):
    """LangChain's own Embeddings interface, satisfied without a network
    call - returns whichever vector was registered for exact text via
    register(), a small default otherwise. Used anywhere a test needs a
    real LangChain VectorStore object (Chroma, etc.) but not a real
    OpenAI call - retriever.py and vector_indexer.py both build one."""

    def __init__(self):
        self._vectors: dict[str, list[float]] = {}

    def register(self, text: str, vector: list[float]) -> None:
        self._vectors[text] = vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(text, [0.0, 0.0]) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectors.get(text, [0.0, 0.0])


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


class FakeChatClient:
    """Stands in for OpenAIChatClient - no network, a canned answer, and a
    record of every call so a test can assert on what was actually asked
    (the question text, the context, temperature/max_tokens)."""

    def __init__(self, model: str = "fake-chat-model", answer: str = "This is a fake grounded answer."):
        self.model = model
        self._answer = answer
        self.calls: list[dict] = []

    def ask(self, question: str, context: str | None = None, temperature: float = 0.0, max_tokens=None) -> str:
        self.calls.append(
            {"question": question, "context": context, "temperature": temperature, "max_tokens": max_tokens}
        )
        return self._answer


class FakeClientGateway:
    """Stands in for ClientGateway - just enough to return a FakeEmbeddingClient/
    FakeChatClient where real code calls get_client_gateway().openai_embedding()/openai_chat()."""

    def __init__(
        self,
        embedding_client: FakeEmbeddingClient | None = None,
        chat_client: FakeChatClient | None = None,
    ):
        self._embedding_client = embedding_client or FakeEmbeddingClient()
        self._chat_client = chat_client or FakeChatClient()

    def openai_embedding(self) -> FakeEmbeddingClient:
        return self._embedding_client

    def openai_chat(self) -> FakeChatClient:
        return self._chat_client


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
        # A test can set score_overrides["chunk_id"] = 1.5 before calling
        # query() to simulate a specific relevance score - real backends
        # compute this from embedding similarity, which this fake doesn't do.
        self.score_overrides: dict[str, float] = {}

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
        # No real similarity math - just echoes back whatever was upserted
        # and matches `where`, up to top_k, in insertion order. Enough to
        # test the *pipeline* around a vector query (retrieval, is_current
        # filtering, filename lookup, dedup) without needing real embeddings
        # to rank against. Only supports the operators this project's own
        # code actually sends: plain equality and {"$ne": value}.
        collection = self.collections.get(collection_name, {})
        ids, documents, metadatas, scores = [], [], [], []
        for chunk_id, entry in collection.items():
            if not self._matches_where(entry["metadata"], where):
                continue
            ids.append(chunk_id)
            documents.append(entry["document"])
            metadatas.append(entry["metadata"])
            scores.append(self.score_overrides.get(chunk_id, 0.9))
            if len(ids) >= top_k:
                break
        return {"ids": [ids], "documents": [documents], "metadatas": [metadatas], "distances": [scores]}

    @staticmethod
    def _matches_where(metadata, where):
        if not where:
            return True
        for key, condition in where.items():
            actual = metadata.get(key)
            if isinstance(condition, dict) and "$ne" in condition:
                if actual == condition["$ne"]:
                    return False
            elif actual != condition:
                return False
        return True

    def delete(self, collection_name, ids):
        self.delete_calls.append({"collection_name": collection_name, "ids": list(ids)})
        collection = self.collections.get(collection_name, {})
        for chunk_id in ids:
            collection.pop(chunk_id, None)

    def update_metadata(self, collection_name, ids, metadatas):
        collection = self.collections.get(collection_name, {})
        for chunk_id, metadata in zip(ids, metadatas, strict=True):
            if chunk_id in collection:
                collection[chunk_id]["metadata"] = metadata

    def health_check(self):
        return {"provider": self.PROVIDER_NAME, "status": "healthy"}


class FakeMetadataStore(BaseMetadataClient):
    """An in-memory metadata store - standing in for SQLiteClient/PostgresClient.
    Documents are kept in a plain dict, keyed by document_id."""

    PROVIDER_NAME = "fake"

    def __init__(self):
        self.documents: dict[str, dict] = {}

    async def create_document(
        self, document_id, filename, file_path, file_size_bytes=0, content_hash="", supersedes=None
    ):
        self.documents[document_id] = {
            "id": document_id,
            "filename": filename,
            "file_path": file_path,
            "status": "uploaded",
            "error_message": None,
            "chunk_ids": None,
            "document_version": 1,
            "file_size_bytes": file_size_bytes,
            "content_hash": content_hash,
            "chunk_count": 0,
            "embedding_model": None,
            "embedding_dimension": None,
            "vector_db": None,
            "chunk_size": None,
            "chunk_overlap": None,
            "last_indexed_at": None,
            "is_current": True,
            "supersedes": supersedes,
            "superseded_by": None,
            "owner": None,
            "department": None,
            "doc_type": None,
            "purpose": None,
            "doc_classification": None,
        }

    async def find_by_content_hash(self, content_hash):
        matches = [doc for doc in self.documents.values() if doc.get("content_hash") == content_hash]
        if not matches:
            return None
        return matches[-1]

    async def delete_document(self, document_id):
        self.documents.pop(document_id, None)

    async def update_status(self, document_id, status, error_message=None):
        if document_id in self.documents:
            self.documents[document_id]["status"] = status
            self.documents[document_id]["error_message"] = error_message

    async def set_chunk_ids(self, document_id, chunk_ids):
        import json

        if document_id in self.documents:
            self.documents[document_id]["chunk_ids"] = json.dumps(chunk_ids)

    async def record_successful_index(
        self,
        document_id,
        chunk_ids,
        embedding_model=None,
        embedding_dimension=None,
        vector_db=None,
        chunk_size=None,
        chunk_overlap=None,
    ):
        import json

        document = self.documents[document_id]
        document["chunk_ids"] = json.dumps(chunk_ids)
        document["chunk_count"] = len(chunk_ids)
        document["embedding_model"] = embedding_model
        document["embedding_dimension"] = embedding_dimension
        document["vector_db"] = vector_db
        document["chunk_size"] = chunk_size
        document["chunk_overlap"] = chunk_overlap
        document["status"] = "indexed"
        document["error_message"] = None
        document["document_version"] += 1
        return document["document_version"]

    async def mark_superseded(self, document_id, superseded_by):
        import json

        document = self.documents.get(document_id)
        if document is None:
            return []
        document["is_current"] = False
        document["superseded_by"] = superseded_by
        return json.loads(document["chunk_ids"]) if document.get("chunk_ids") else []

    async def record_document_metadata(self, document_id, owner, department, doc_type, purpose, doc_classification):
        document = self.documents.get(document_id)
        if document is not None:
            document["owner"] = owner
            document["department"] = department
            document["doc_type"] = doc_type
            document["purpose"] = purpose
            document["doc_classification"] = doc_classification

    async def get_document(self, document_id):
        return self.documents.get(document_id)

    async def list_documents(self):
        return list(self.documents.values())

    def health_check(self):
        return {"provider": self.PROVIDER_NAME, "status": "healthy"}


class FakeDBGateway:
    """Stands in for DBGateway - returns the one FakeVectorStore/FakeMetadataStore
    given to it regardless of provider name. A test needing two distinct
    providers should use two FakeDBGateway instances instead."""

    def __init__(self, vector_store: FakeVectorStore | None = None, metadata_store: FakeMetadataStore | None = None):
        self._vector_store = vector_store or FakeVectorStore()
        self._metadata_store = metadata_store or FakeMetadataStore()

    def vector_store(self, provider=None):
        return self._vector_store

    def metadata_store(self, provider=None):
        return self._metadata_store
