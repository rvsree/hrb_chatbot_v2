"""Tests for retrieve_chunks() (ai/rag_pipeline/query_retrieval/retriever.py).
Covers the two things this module actually does beyond calling the vector
store directly: deduplicating chunks found by more than one sub-query, and
attaching each chunk's source filename (for citations) with one metadata
lookup per distinct document, not per chunk. Uses fakes from conftest.py."""

from src.hrb_chatbot.ai.rag_pipeline.query_retrieval import retriever
from tests.conftest import FakeClientGateway, FakeDBGateway, FakeMetadataStore, FakeVectorStore


async def _seed_chunk(vector_store, metadata_store, document_id, chunk_index, filename, text="chunk text"):
    if document_id not in [d["id"] for d in metadata_store.documents.values()]:
        await metadata_store.create_document(document_id, filename, f"data/uploads/{document_id}/{filename}")
    chunk_id = f"{document_id}:{chunk_index}"
    vector_store.upsert(
        collection_name=retriever.COLLECTION_NAME,
        ids=[chunk_id],
        documents=[text],
        embeddings=[[0.1]],
        metadatas=[{"document_id": document_id, "chunk_index": chunk_index}],
    )


async def test_retrieved_chunks_have_their_source_filename_attached(monkeypatch):
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())

    await _seed_chunk(vector_store, metadata_store, "doc-1", 0, "policy.pdf", text="Parental leave is 16 weeks.")

    chunks = await retriever.retrieve_chunks(["How much parental leave?"], top_k=5)

    assert len(chunks) == 1
    assert chunks[0]["filename"] == "policy.pdf"
    assert chunks[0]["document_id"] == "doc-1"
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["text"] == "Parental leave is 16 weeks."


async def test_the_same_chunk_found_by_two_subqueries_is_not_duplicated(monkeypatch):
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())

    await _seed_chunk(vector_store, metadata_store, "doc-1", 0, "policy.pdf")

    # Two different sub-queries - FakeVectorStore.query() has no real
    # similarity math, so both "find" the same one seeded chunk. The
    # dedup-by-(document_id, chunk_index) logic must collapse this to one.
    chunks = await retriever.retrieve_chunks(["sub-question A", "sub-question B"], top_k=5)

    assert len(chunks) == 1


async def test_a_chunk_whose_document_metadata_is_missing_gets_a_placeholder_filename(monkeypatch):
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())

    # A chunk exists in the vector store, but its document row was never
    # created (or was deleted) - retrieval must not crash on this.
    vector_store.upsert(
        collection_name=retriever.COLLECTION_NAME,
        ids=["orphan-doc:0"],
        documents=["orphaned chunk text"],
        embeddings=[[0.1]],
        metadatas=[{"document_id": "orphan-doc", "chunk_index": 0}],
    )

    chunks = await retriever.retrieve_chunks(["any question"], top_k=5)

    assert chunks[0]["filename"] == "unknown"


async def test_superseded_chunks_are_excluded_from_retrieval(monkeypatch):
    """The core multi-version-retrieval correctness case: a chunk explicitly
    marked is_current=false (superseded) must never come back from a normal
    query, even though it's still physically present in the vector store."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())

    await metadata_store.create_document("doc-old", "policy-v1.pdf", "data/uploads/doc-old/policy-v1.pdf")
    vector_store.upsert(
        collection_name=retriever.COLLECTION_NAME,
        ids=["doc-old:0"],
        documents=["stale policy text"],
        embeddings=[[0.1]],
        metadatas=[{"document_id": "doc-old", "chunk_index": 0, "is_current": False}],
    )
    await _seed_chunk(vector_store, metadata_store, "doc-new", 0, "policy-v2.pdf", text="current policy text")

    chunks = await retriever.retrieve_chunks(["policy question"], top_k=5)

    document_ids = [chunk["document_id"] for chunk in chunks]
    assert "doc-old" not in document_ids
    assert "doc-new" in document_ids


async def test_chunks_with_no_is_current_field_at_all_are_still_retrieved(monkeypatch):
    """Backward compatibility: chunks indexed before is_current existed have
    no such key in their metadata at all - an equality filter would wrongly
    exclude them too; only an explicit false should be excluded."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())

    # No is_current key at all - simulates a pre-existing chunk from before this field.
    await _seed_chunk(vector_store, metadata_store, "doc-legacy", 0, "old-upload.pdf")

    chunks = await retriever.retrieve_chunks(["any question"], top_k=5)

    assert len(chunks) == 1
    assert chunks[0]["document_id"] == "doc-legacy"


async def test_a_chunk_worse_than_the_relevance_bar_is_excluded(monkeypatch):
    """The real bug this guards against: a question with nothing relevant
    indexed still returns top_k results (vector search has no built-in
    "good enough") - without this filter, those poor matches show up as
    misleading "sources" next to an answer that correctly says it doesn't
    know. See MAX_CHROMA_DISTANCE's own comment for the real scores this
    was calibrated against."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())
    # FakeVectorStore.PROVIDER_NAME is "fake", not "chromadb" - it falls
    # through to the same lower-is-better branch _meets_relevance_bar() uses
    # for Chroma, which is what's being tested here.

    await _seed_chunk(vector_store, metadata_store, "doc-relevant", 0, "policy.pdf", text="a good match")
    await _seed_chunk(vector_store, metadata_store, "doc-irrelevant", 0, "unrelated.pdf", text="a bad match")
    vector_store.score_overrides["doc-relevant:0"] = 0.75  # inside the "good match" cluster
    vector_store.score_overrides["doc-irrelevant:0"] = 1.25  # inside the "bad match" cluster

    chunks = await retriever.retrieve_chunks(["some question"], top_k=5)

    document_ids = [chunk["document_id"] for chunk in chunks]
    assert "doc-relevant" in document_ids
    assert "doc-irrelevant" not in document_ids


async def test_when_every_retrieved_chunk_fails_the_relevance_bar_result_is_empty(monkeypatch):
    """Confirms the empty-list path actually triggers - generate_answer()'s
    own no-chunks short-circuit (response_generation/generator.py) then
    kicks in downstream, skipping the LLM call entirely rather than
    generating from irrelevant context."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())

    await _seed_chunk(vector_store, metadata_store, "doc-1", 0, "unrelated.pdf")
    vector_store.score_overrides["doc-1:0"] = 1.9

    chunks = await retriever.retrieve_chunks(["some question nothing indexed answers"], top_k=5)

    assert chunks == []


async def test_top_k_limits_how_many_chunks_come_back(monkeypatch):
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(retriever, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(retriever, "get_client_gateway", lambda: FakeClientGateway())

    for i in range(5):
        await _seed_chunk(vector_store, metadata_store, "doc-1", i, "policy.pdf")

    chunks = await retriever.retrieve_chunks(["a question"], top_k=2)

    assert len(chunks) == 2
