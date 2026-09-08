"""Tests for write_chunks() - ai/doc_processing/indexing/vector_indexer.py.

This is the highest-value file to test in the indexing pipeline: it's the
one place that decides insert vs. update, and the one place responsible
for deleting stale chunks when a re-indexed document shrinks - a real bug
class (orphaned vectors pointing at content that no longer exists) that's
easy to reintroduce silently in a future edit if nothing catches it.

Uses FakeVectorStore/FakeMetadataStore/FakeDBGateway from
tests/conftest.py - no real ChromaDB or SQLite involved, `write_chunks()`
is `async def`, so every test that calls it is too (pytest-asyncio runs
these because of the `asyncio_mode = auto` setting in pytest.ini).
"""

from src.hrb_chatbot.ai.doc_processing.indexing import vector_indexer
from tests.conftest import FakeDBGateway, FakeMetadataStore, FakeVectorStore


async def test_first_index_of_a_document_is_reported_as_insert(monkeypatch):
    gateway = FakeDBGateway()
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    result = await vector_indexer.write_chunks(
        "doc-1", ["chunk one text", "chunk two text"], [[0.1, 0.2], [0.3, 0.4]]
    )

    assert result["action"] == "insert"
    assert result["chunks_indexed"] == 2
    assert result["chunks_removed"] == 0


async def test_reindexing_the_same_document_is_reported_as_update(monkeypatch):
    gateway = FakeDBGateway()
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    # A document row has to exist before it can be indexed - real usage
    # always uploads first (documents_service.save_upload() calls
    # create_document()), then indexes. Skipping this step is exactly what
    # made this test fail the first time it was run: set_chunk_ids() on a
    # nonexistent row does nothing, the same way a real "UPDATE ... WHERE
    # id = ?" does nothing against a row that was never inserted.
    await gateway.metadata_store().create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")

    await vector_indexer.write_chunks("doc-1", ["chunk one", "chunk two"], [[0.1], [0.2]])
    result = await vector_indexer.write_chunks("doc-1", ["chunk one v2", "chunk two v2"], [[0.1], [0.2]])

    assert result["action"] == "update"


async def test_reindexing_a_shrunken_document_deletes_the_now_stale_chunks(monkeypatch):
    """The core correctness case: a document that produced 5 chunks last
    time and only 2 chunks this time must not leave the extra 3 sitting in
    the vector store forever - see vector_indexer.py's own module
    docstring for why this needs explicit cleanup, not just an upsert."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    # Same reasoning as the previous test - a document row must exist
    # before indexing, matching real usage (upload always happens first).
    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")

    five_chunks = ["chunk " + str(i) for i in range(5)]
    five_embeddings = [[0.1] for _ in range(5)]
    await vector_indexer.write_chunks("doc-1", five_chunks, five_embeddings)

    assert len(vector_store.collections[vector_indexer.COLLECTION_NAME]) == 5

    two_chunks = ["chunk 0 v2", "chunk 1 v2"]
    two_embeddings = [[0.1], [0.2]]
    result = await vector_indexer.write_chunks("doc-1", two_chunks, two_embeddings)

    assert result["action"] == "update"
    assert result["chunks_indexed"] == 2
    assert result["chunks_removed"] == 3
    # The real proof, not just the reported numbers: only 2 chunks should
    # actually remain in the fake vector store afterward, matching the
    # same "prove it with a real count, not just a returned report"
    # discipline this project already uses (see docs/RAG-ROADMAP.md's
    # Phase 4 notes on why a completely correct-looking report once hid a
    # real double-execution bug).
    assert len(vector_store.collections[vector_indexer.COLLECTION_NAME]) == 2


async def test_chunk_ids_are_deterministic_by_document_and_position():
    ids = vector_indexer.build_chunk_ids("doc-abc", 3)
    assert ids == ["doc-abc:0", "doc-abc:1", "doc-abc:2"]
