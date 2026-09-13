"""Tests for retrieve_chunks() (ai/rag_pipeline/query_retrieval/retriever.py).

retriever.py now builds a real LangChain Chroma/PineconeVectorStore around
this project's vector store client (Phase 4, LangChain) - it can no longer
be tested against conftest.py's plain-dict FakeVectorStore the way the old
raw-client version could (same reasoning test_vector_indexer.py's real
EphemeralChromaVectorStore was needed in Phase 3). Uses a real, ephemeral
(in-memory, zero network) chromadb collection, plus a FakeEmbeddings that
returns hand-registered vectors instead of calling OpenAI - real vector
similarity math runs, but nothing here spends real API cost or needs a key,
same reasoning this project already applies elsewhere.

Each test gets its own uuid-suffixed collection name (monkeypatched onto
retriever.COLLECTION_NAME) - ephemeral chromadb clients turned out to still
share collection storage by literal name within one test process (found the
hard way in Phase 3's test_vector_indexer.py), so a fresh client alone
isn't enough isolation.
"""

import uuid

import chromadb
from langchain_core.embeddings import Embeddings

from src.hrb_chatbot.ai.rag_pipeline.query_retrieval import retriever
from tests.conftest import FakeDBGateway, FakeMetadataStore


class FakeEmbeddings(Embeddings):
    """Returns whichever vector was registered for exact text via
    register() - a small default otherwise. No network call."""

    def __init__(self):
        self._vectors: dict[str, list[float]] = {}

    def register(self, text: str, vector: list[float]) -> None:
        self._vectors[text] = vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(text, [0.0, 0.0]) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectors.get(text, [0.0, 0.0])


class FakeVectorStoreClient:
    """Stands in for ChromaDBClient - a real, ephemeral chromadb client
    (get_client(), what retriever.py's _vector_store() actually needs for
    the Chroma path), not something that only duck-types BaseVectorDBClient."""

    PROVIDER_NAME = "chromadb"

    def __init__(self):
        self._client = chromadb.EphemeralClient()

    def get_client(self):
        return self._client


def _seed_collection(fake_vector_store_client, collection_name: str, chunks: list[dict]) -> None:
    """chunks: list of {id, text, embedding, metadata} - written directly
    into the real ephemeral collection, bypassing the whole indexing
    pipeline (not what's under test here)."""
    collection = fake_vector_store_client.get_client().get_or_create_collection(collection_name)
    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )


def _setup(monkeypatch):
    """Common setup every test needs: a fresh, isolated collection name, a
    real ephemeral Chroma client, a fake metadata store, and a fake
    embeddings object retriever.py will use instead of calling OpenAI."""
    collection_name = f"test_{uuid.uuid4().hex}"
    monkeypatch.setattr(retriever, "COLLECTION_NAME", collection_name)

    vector_store_client = FakeVectorStoreClient()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store_client, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)

    embeddings = FakeEmbeddings()
    monkeypatch.setattr(retriever, "_embeddings", lambda: embeddings)

    return collection_name, vector_store_client, metadata_store, embeddings


async def test_retrieved_chunks_have_their_source_filename_attached(monkeypatch):
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        [
            {
                "id": "doc-1:0",
                "text": "Parental leave is 16 weeks.",
                "embedding": [1.0, 0.0],
                "metadata": {"document_id": "doc-1", "chunk_index": 0, "is_current": True},
            }
        ],
    )
    embeddings.register("How much parental leave?", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["How much parental leave?"], top_k=5)

    assert len(chunks) == 1
    assert chunks[0]["filename"] == "policy.pdf"
    assert chunks[0]["document_id"] == "doc-1"
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["text"] == "Parental leave is 16 weeks."
    assert chunks[0]["score"] is not None


async def test_the_same_chunk_found_by_two_subqueries_is_not_duplicated(monkeypatch):
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        [{"id": "doc-1:0", "text": "chunk text", "embedding": [1.0, 0.0], "metadata": {"document_id": "doc-1", "chunk_index": 0}}],
    )
    # Both sub-queries embed to the same vector, so both "find" the one seeded
    # chunk - the dedup-by-(document_id, chunk_index) logic must collapse this to one.
    embeddings.register("sub-question A", [1.0, 0.0])
    embeddings.register("sub-question B", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["sub-question A", "sub-question B"], top_k=5)

    assert len(chunks) == 1


async def test_a_chunk_whose_document_metadata_is_missing_gets_a_placeholder_filename(monkeypatch):
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    # A chunk exists in the vector store, but its document row was never
    # created (or was deleted) - retrieval must not crash on this.
    _seed_collection(
        vector_store_client,
        collection_name,
        [{"id": "orphan-doc:0", "text": "orphaned chunk text", "embedding": [1.0, 0.0], "metadata": {"document_id": "orphan-doc", "chunk_index": 0}}],
    )
    embeddings.register("any question", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["any question"], top_k=5)

    assert chunks[0]["filename"] == "unknown"


async def test_superseded_chunks_are_excluded_from_retrieval(monkeypatch):
    """The core multi-version-retrieval correctness case: a chunk explicitly
    marked is_current=false (superseded) must never come back from a normal
    query, even though it's still physically present in the vector store."""
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-old", "policy-v1.pdf", "data/uploads/doc-old/policy-v1.pdf")
    await metadata_store.create_document("doc-new", "policy-v2.pdf", "data/uploads/doc-new/policy-v2.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        [
            {"id": "doc-old:0", "text": "stale policy text", "embedding": [1.0, 0.0], "metadata": {"document_id": "doc-old", "chunk_index": 0, "is_current": False}},
            {"id": "doc-new:0", "text": "current policy text", "embedding": [1.0, 0.0], "metadata": {"document_id": "doc-new", "chunk_index": 0, "is_current": True}},
        ],
    )
    embeddings.register("policy question", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["policy question"], top_k=5)

    document_ids = [chunk["document_id"] for chunk in chunks]
    assert "doc-old" not in document_ids
    assert "doc-new" in document_ids


async def test_chunks_with_no_is_current_field_at_all_are_still_retrieved(monkeypatch):
    """Backward compatibility: chunks indexed before is_current existed have
    no such key in their metadata at all - an equality filter would wrongly
    exclude them too; only an explicit false should be excluded."""
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-legacy", "old-upload.pdf", "data/uploads/doc-legacy/old-upload.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        # No is_current key at all - simulates a pre-existing chunk from before this field.
        [{"id": "doc-legacy:0", "text": "legacy chunk", "embedding": [1.0, 0.0], "metadata": {"document_id": "doc-legacy", "chunk_index": 0}}],
    )
    embeddings.register("any question", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["any question"], top_k=5)

    assert len(chunks) == 1
    assert chunks[0]["document_id"] == "doc-legacy"


async def test_a_chunk_worse_than_the_relevance_bar_is_excluded(monkeypatch):
    """The real bug this guards against: a question with nothing relevant
    indexed still returns top_k results (vector search has no built-in
    "good enough") - without this filter, those poor matches show up as
    misleading "sources" next to an answer that correctly says it doesn't
    know. See MAX_CHROMA_DISTANCE's own comment for the real scores this
    was calibrated against. Only similarity search has a real per-chunk
    score to compare against - this only applies to that strategy."""
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-relevant", "policy.pdf", "data/uploads/doc-relevant/policy.pdf")
    await metadata_store.create_document("doc-irrelevant", "unrelated.pdf", "data/uploads/doc-irrelevant/unrelated.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        [
            # Identical to the query vector - distance ~0, well inside the bar.
            {"id": "doc-relevant:0", "text": "a good match", "embedding": [1.0, 0.0], "metadata": {"document_id": "doc-relevant", "chunk_index": 0}},
            # Far from the query vector - L2 distance well past MAX_CHROMA_DISTANCE (1.1).
            {"id": "doc-irrelevant:0", "text": "a bad match", "embedding": [10.0, 10.0], "metadata": {"document_id": "doc-irrelevant", "chunk_index": 0}},
        ],
    )
    embeddings.register("some question", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["some question"], top_k=5)

    document_ids = [chunk["document_id"] for chunk in chunks]
    assert "doc-relevant" in document_ids
    assert "doc-irrelevant" not in document_ids


async def test_when_every_retrieved_chunk_fails_the_relevance_bar_result_is_empty(monkeypatch):
    """Confirms the empty-list path actually triggers - generate_answer()'s
    own no-chunks short-circuit (response_generation/generator.py) then
    kicks in downstream, skipping the LLM call entirely rather than
    generating from irrelevant context."""
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-1", "unrelated.pdf", "data/uploads/doc-1/unrelated.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        [{"id": "doc-1:0", "text": "totally unrelated", "embedding": [50.0, 50.0], "metadata": {"document_id": "doc-1", "chunk_index": 0}}],
    )
    embeddings.register("some question nothing indexed answers", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["some question nothing indexed answers"], top_k=5)

    assert chunks == []


async def test_top_k_limits_how_many_chunks_come_back(monkeypatch):
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        [
            {"id": f"doc-1:{i}", "text": f"chunk {i}", "embedding": [1.0, 0.0], "metadata": {"document_id": "doc-1", "chunk_index": i}}
            for i in range(5)
        ],
    )
    embeddings.register("a question", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["a question"], top_k=2)

    assert len(chunks) == 2


async def test_mmr_search_strategy_returns_chunks_with_a_null_score(monkeypatch):
    """LangChain's max_marginal_relevance_search() does not return a
    per-chunk score at all, unlike similarity_search_with_score() -
    RetrievedChunk.score is null for MMR results, not a made-up number."""
    collection_name, vector_store_client, metadata_store, embeddings = _setup(monkeypatch)
    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    _seed_collection(
        vector_store_client,
        collection_name,
        [{"id": "doc-1:0", "text": "chunk text", "embedding": [1.0, 0.0], "metadata": {"document_id": "doc-1", "chunk_index": 0}}],
    )
    embeddings.register("a question", [1.0, 0.0])

    chunks = await retriever.retrieve_chunks(["a question"], top_k=5, search_strategy="mmr")

    assert len(chunks) == 1
    assert chunks[0]["score"] is None


async def test_unknown_search_strategy_raises_value_error(monkeypatch):
    _setup(monkeypatch)

    try:
        await retriever.retrieve_chunks(["a question"], top_k=5, search_strategy="not-a-real-strategy")
        assert False, "expected a ValueError"
    except ValueError as error:
        assert "not-a-real-strategy" in str(error)
