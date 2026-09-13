"""Tests for write_chunks() (ai/doc_processing/indexing/vector_indexer.py).
Covers the highest-value logic in the indexing pipeline: insert vs. update,
and deleting stale chunks when a re-indexed document shrinks (guards
against orphaned vectors). Uses fakes from conftest.py; write_chunks() is
async, so tests are too (pytest-asyncio's asyncio_mode=auto)."""

from src.hrb_chatbot.ai.doc_processing.indexing import vector_indexer
from tests.conftest import FakeDBGateway, FakeMetadataStore, FakeVectorStore


async def test_first_index_of_a_document_is_reported_as_insert(monkeypatch):
    gateway = FakeDBGateway()
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    # A document row must exist before indexing (real usage uploads first,
    # then indexes) - record_successful_index() acts on an existing row.
    await gateway.metadata_store().create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")

    result = await vector_indexer.write_chunks(
        "doc-1", ["chunk one text", "chunk two text"], [[0.1, 0.2], [0.3, 0.4]]
    )

    assert result["action"] == "insert"
    assert result["chunks_indexed"] == 2
    assert result["chunks_removed"] == 0
    assert result["embedding_dimension"] == 2
    assert result["document_version"] == 2


async def test_reindexing_the_same_document_is_reported_as_update(monkeypatch):
    gateway = FakeDBGateway()
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    # A document row must exist before indexing (real usage uploads first,
    # then indexes) - set_chunk_ids() on a nonexistent row silently does nothing.
    await gateway.metadata_store().create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")

    await vector_indexer.write_chunks("doc-1", ["chunk one", "chunk two"], [[0.1], [0.2]])
    result = await vector_indexer.write_chunks("doc-1", ["chunk one v2", "chunk two v2"], [[0.1], [0.2]])

    assert result["action"] == "update"


async def test_reindexing_a_shrunken_document_deletes_the_now_stale_chunks(monkeypatch):
    """Core correctness case: a document that shrinks from 5 chunks to 2
    must not leave the extra 3 sitting in the vector store forever."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    # Same reasoning as above - a document row must exist before indexing.
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
    # Proof beyond the reported numbers: only 2 chunks should actually
    # remain in the fake vector store (guards against a report that looks
    # correct while masking a real double-execution bug).
    assert len(vector_store.collections[vector_indexer.COLLECTION_NAME]) == 2


async def test_chunk_ids_are_deterministic_by_document_and_position():
    ids = vector_indexer.build_chunk_ids("doc-abc", 3)
    assert ids == ["doc-abc:0", "doc-abc:1", "doc-abc:2"]


async def test_new_chunks_are_tagged_is_current_true_with_a_timestamp(monkeypatch):
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    await vector_indexer.write_chunks("doc-1", ["chunk one"], [[0.1]])

    metadata = vector_store.collections[vector_indexer.COLLECTION_NAME]["doc-1:0"]["metadata"]
    assert metadata["is_current"] is True
    assert metadata["indexed_at"]  # a real timestamp string, not empty/missing


async def test_superseding_document_flips_the_old_documents_chunks_to_not_current(monkeypatch):
    """Core correctness case for document versioning: once the new document
    (doc-2, which supersedes doc-1) successfully indexes, doc-1's chunks
    must be marked is_current=false in both SQL and the vector store - not
    deleted, but excluded from normal retrieval."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    await metadata_store.create_document("doc-1", "policy-v1.pdf", "data/uploads/doc-1/policy-v1.pdf")
    await vector_indexer.write_chunks("doc-1", ["old chunk a", "old chunk b"], [[0.1], [0.2]])

    await metadata_store.create_document(
        "doc-2", "policy-v2.pdf", "data/uploads/doc-2/policy-v2.pdf", supersedes="doc-1"
    )
    await vector_indexer.write_chunks("doc-2", ["new chunk a"], [[0.3]])

    # SQL side: doc-1 flipped to not current, doc-2 knows nothing changed about it.
    old_document = await metadata_store.get_document("doc-1")
    assert old_document["is_current"] is False
    assert old_document["superseded_by"] == "doc-2"

    # Vector-store side: doc-1's OWN chunks flipped too - doc-1's data still
    # exists (not deleted, available for audit), just excluded from retrieval.
    old_chunk_metadata = vector_store.collections[vector_indexer.COLLECTION_NAME]["doc-1:0"]["metadata"]
    assert old_chunk_metadata["is_current"] is False
    assert "doc-1:0" in vector_store.collections[vector_indexer.COLLECTION_NAME]  # still present, not deleted

    # doc-2's own chunks are unaffected - still current.
    new_chunk_metadata = vector_store.collections[vector_indexer.COLLECTION_NAME]["doc-2:0"]["metadata"]
    assert new_chunk_metadata["is_current"] is True


async def test_reindexing_a_document_does_not_repeat_the_supersede_flip(monkeypatch):
    """The supersede propagation only runs on the *first* successful index
    (action == "insert") - re-indexing doc-2 again must not re-process
    doc-1, which by then may have been re-uploaded or deleted."""
    vector_store = FakeVectorStore()
    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=vector_store, metadata_store=metadata_store)
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)

    await metadata_store.create_document("doc-1", "policy-v1.pdf", "data/uploads/doc-1/policy-v1.pdf")
    await vector_indexer.write_chunks("doc-1", ["old chunk"], [[0.1]])

    await metadata_store.create_document(
        "doc-2", "policy-v2.pdf", "data/uploads/doc-2/policy-v2.pdf", supersedes="doc-1"
    )
    await vector_indexer.write_chunks("doc-2", ["new chunk"], [[0.2]])
    # Manually restore doc-1 to current, as if it were a fresh, unrelated
    # upload again - a second index of doc-2 must NOT flip it back to false.
    metadata_store.documents["doc-1"]["is_current"] = True

    await vector_indexer.write_chunks("doc-2", ["new chunk v2"], [[0.3]])

    assert metadata_store.documents["doc-1"]["is_current"] is True
