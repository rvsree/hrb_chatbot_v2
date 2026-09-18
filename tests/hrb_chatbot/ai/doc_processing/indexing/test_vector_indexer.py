"""Tests for write_chunks() (ai/doc_processing/indexing/vector_indexer.py).

Covers the highest-value logic in the indexing pipeline: insert vs. update,
skip-if-unchanged (a chunk whose content didn't change is left alone, not
re-embedded), and cleaning up stale chunks when a re-indexed document
shrinks or changes (guards against orphaned vectors). write_chunks() is
async, so tests are too (pytest-asyncio's asyncio_mode=auto).

Phase 17 rewrote write_chunks() onto LangChain's own index() + a real
SQLRecordManager (a real, ephemeral SQLite file, deleted at the end of
each test - RecordManager needs a real file, not an in-memory fake, since
it does its own SQL work). The vector store side uses a real, in-memory
chromadb.EphemeralClient() wrapped in LangChain's own Chroma class -
index() needs a real LangChain VectorStore object, not conftest.py's
plain-dict FakeVectorStore - plus conftest.py's FakeEmbeddings so index()'s
own internal embedding calls don't hit OpenAI. Zero network, zero cost,
same reasoning this project already applies everywhere else.
"""

import json
import tempfile
import uuid
from pathlib import Path

import chromadb
from langchain_chroma import Chroma

from src.hrb_chatbot.ai.doc_processing.indexing import vector_indexer
from tests.conftest import FakeDBGateway, FakeEmbeddings, FakeMetadataStore


class _RawChromaForSupersede:
    """Stands in for gateway.vector_store(provider=...) - only used by
    write_chunks()'s supersede-flip step, which calls update_metadata()
    directly (not through LangChain) exactly as before Phase 17. Wraps the
    same real chromadb collection the LangChain Chroma object below writes
    into, so both sides see the same data."""

    PROVIDER_NAME = "chromadb"

    def __init__(self, raw_collection):
        self._collection = raw_collection

    def update_metadata(self, collection_name: str, ids: list[str], metadatas: list[dict]) -> None:
        self._collection.update(ids=ids, metadatas=metadatas)


def _new_test_setup():
    """One real, isolated ephemeral chromadb collection + a real (temp-file)
    SQLRecordManager, wired into write_chunks() via monkeypatch-free fakes -
    everything write_chunks() touches (get_db_gateway(), get_vector_store(),
    the record manager's db path) is swapped for a test double or a real,
    throwaway file. Returns (metadata_store, raw_collection, cleanup)."""
    suffix = uuid.uuid4().hex
    collection_name = f"hrb_chatbot_kb_test_{suffix}"

    chroma_client = chromadb.EphemeralClient()
    raw_collection = chroma_client.get_or_create_collection(collection_name)
    embeddings = FakeEmbeddings()
    langchain_store = Chroma(client=chroma_client, collection_name=collection_name, embedding_function=embeddings)

    metadata_store = FakeMetadataStore()
    gateway = FakeDBGateway(vector_store=_RawChromaForSupersede(raw_collection), metadata_store=metadata_store)

    record_manager_db = Path(tempfile.mktemp(suffix=".sqlite3"))

    def cleanup():
        # Best-effort - SQLAlchemy keeps its own connection to this file
        # open, which on Windows blocks deleting it until that connection
        # is closed; not worth chasing down just to tidy a temp file
        # (same "ignore_errors" reasoning documents_service.py's own
        # shutil.rmtree(..., ignore_errors=True) already uses).
        try:
            record_manager_db.unlink(missing_ok=True)
        except PermissionError:
            pass

    return metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup


def _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db):
    monkeypatch.setattr(vector_indexer, "get_db_gateway", lambda: gateway)
    monkeypatch.setattr(
        vector_indexer, "get_vector_store", lambda vector_db, embedding_model=None: (langchain_store, "chromadb")
    )
    monkeypatch.setattr(vector_indexer, "COLLECTION_NAME", collection_name)
    monkeypatch.setattr(vector_indexer, "RECORD_MANAGER_DB_URL", f"sqlite:///{record_manager_db}")


async def test_first_index_of_a_document_is_reported_as_insert(monkeypatch):
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    result = await vector_indexer.write_chunks("doc-1", ["alpha", "beta"])

    assert result["action"] == "insert"
    assert result["chunks_indexed"] == 2
    assert result["chunks_removed"] == 0
    assert result["embedding_dimension"] > 0
    assert result["document_version"] == 2
    cleanup()


async def test_reindexing_with_identical_content_skips_and_reports_zero_new_chunks(monkeypatch):
    """The actual point of Phase 17: re-indexing unchanged content doesn't
    re-embed or re-write anything - chunks_indexed reflects that."""
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    await vector_indexer.write_chunks("doc-1", ["alpha", "beta"])
    result = await vector_indexer.write_chunks("doc-1", ["alpha", "beta"])

    assert result["action"] == "update"
    assert result["chunks_indexed"] == 0  # both chunks unchanged - nothing added or updated
    assert result["chunks_removed"] == 0
    cleanup()


async def test_reindexing_with_one_changed_chunk_only_touches_that_chunk(monkeypatch):
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    await vector_indexer.write_chunks("doc-1", ["alpha", "beta"])
    result = await vector_indexer.write_chunks("doc-1", ["alpha", "beta changed"])

    assert result["action"] == "update"
    assert result["chunks_indexed"] == 1  # only "beta changed" is new
    assert result["chunks_removed"] == 1  # the old "beta" chunk is gone
    cleanup()


async def test_reindexing_a_shrunken_document_deletes_the_now_stale_chunks(monkeypatch):
    """Core correctness case: a document that shrinks from 3 chunks to 1
    must not leave the extra 2 sitting in the vector store forever."""
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    await vector_indexer.write_chunks("doc-1", ["alpha", "beta", "gamma"])
    result = await vector_indexer.write_chunks("doc-1", ["alpha v2"])

    assert result["action"] == "update"
    assert result["chunks_indexed"] == 1
    assert result["chunks_removed"] == 3  # none of the original 3 survive - all content changed or gone
    cleanup()


async def test_new_chunks_are_tagged_is_current_true_with_a_timestamp(monkeypatch):
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    await vector_indexer.write_chunks("doc-1", ["alpha"])

    document = await metadata_store.get_document("doc-1")

    chunk_id = json.loads(document["chunk_ids"])[0]
    got = langchain_store.get(ids=[chunk_id])
    metadata = got["metadatas"][0]

    assert metadata["is_current"] is True
    assert metadata["indexed_at"]  # a real timestamp string, not empty/missing
    assert metadata["document_id"] == "doc-1"
    assert metadata["chunk_index"] == 0
    cleanup()


async def test_chunk_id_changes_when_content_changes_same_position(monkeypatch):
    # This is *why* skip-if-unchanged works at all - see build_chunk_id()'s
    # own docstring.
    id_a = vector_indexer.build_chunk_id("doc-1", 0, "original text")
    id_b = vector_indexer.build_chunk_id("doc-1", 0, "different text")
    id_same = vector_indexer.build_chunk_id("doc-1", 0, "original text")
    assert id_a != id_b
    assert id_a == id_same
    assert id_a.startswith("doc-1:0:")


async def test_superseding_document_flips_the_old_documents_chunks_to_not_current(monkeypatch):
    """Core correctness case for document versioning: once the new document
    (doc-2, which supersedes doc-1) successfully indexes, doc-1's chunks
    must be marked is_current=false in both SQL and the vector store - not
    deleted, but excluded from normal retrieval. chunk_index must survive
    the flip too - update_metadata() replaces the full metadata dict, so a
    dropped field here would silently vanish, not just fail loudly."""
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy-v1.pdf", "data/uploads/doc-1/policy-v1.pdf")
    await vector_indexer.write_chunks("doc-1", ["old chunk a", "old chunk b"])

    await metadata_store.create_document(
        "doc-2", "policy-v2.pdf", "data/uploads/doc-2/policy-v2.pdf", supersedes="doc-1"
    )
    await vector_indexer.write_chunks("doc-2", ["new chunk a"])

    old_document = await metadata_store.get_document("doc-1")
    assert old_document["is_current"] is False
    assert old_document["superseded_by"] == "doc-2"


    old_chunk_ids = json.loads(old_document["chunk_ids"])
    got = langchain_store.get(ids=old_chunk_ids)
    metadatas_by_id = dict(zip(got["ids"], got["metadatas"], strict=True))
    for chunk_id in old_chunk_ids:
        metadata = metadatas_by_id[chunk_id]
        assert metadata["is_current"] is False
        assert metadata["document_id"] == "doc-1"
        assert metadata["chunk_index"] in (0, 1)  # preserved, not dropped by the metadata replace

    new_document = await metadata_store.get_document("doc-2")
    new_chunk_id = json.loads(new_document["chunk_ids"])[0]
    new_metadata = langchain_store.get(ids=[new_chunk_id])["metadatas"][0]
    assert new_metadata["is_current"] is True
    cleanup()


async def test_reindexing_a_document_does_not_repeat_the_supersede_flip(monkeypatch):
    """The supersede propagation only runs on the *first* successful index
    (action == "insert") - re-indexing doc-2 again must not re-process
    doc-1, which by then may have been re-uploaded or deleted."""
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy-v1.pdf", "data/uploads/doc-1/policy-v1.pdf")
    await vector_indexer.write_chunks("doc-1", ["old chunk"])

    await metadata_store.create_document(
        "doc-2", "policy-v2.pdf", "data/uploads/doc-2/policy-v2.pdf", supersedes="doc-1"
    )
    await vector_indexer.write_chunks("doc-2", ["new chunk"])
    # Manually restore doc-1 to current, as if it were a fresh, unrelated
    # upload again - a second index of doc-2 must NOT flip it back to false.
    metadata_store.documents["doc-1"]["is_current"] = True

    await vector_indexer.write_chunks("doc-2", ["new chunk v2"])

    assert metadata_store.documents["doc-1"]["is_current"] is True
    cleanup()


async def test_first_index_writes_chunks_with_no_doc_type_fields_yet(monkeypatch):
    """Phase 19: a first index doesn't know doc_type/department/doc_classification
    yet (extraction hasn't run - see pipeline.py), so those keys are simply
    absent from the chunk metadata, not present-with-null."""
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    result = await vector_indexer.write_chunks("doc-1", ["alpha"])

    assert result["chunk_ids"] == json.loads((await metadata_store.get_document("doc-1"))["chunk_ids"])
    metadata = langchain_store.get(ids=result["chunk_ids"])["metadatas"][0]
    assert "doc_type" not in metadata
    assert "department" not in metadata
    assert "doc_classification" not in metadata
    cleanup()


async def test_reindex_carries_forward_doc_type_fields_already_known_from_sql(monkeypatch):
    """Phase 19: on a re-index, doc_type/department/doc_classification are
    already sitting in existing_document (extracted on the first index) -
    write_chunks() must put them straight into the new chunk metadata, no
    follow-up call needed."""
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    await vector_indexer.write_chunks("doc-1", ["alpha"])
    metadata_store.documents["doc-1"]["doc_type"] = "benefits"
    metadata_store.documents["doc-1"]["department"] = "HR"
    metadata_store.documents["doc-1"]["doc_classification"] = "401k"

    result = await vector_indexer.write_chunks("doc-1", ["alpha v2"])

    metadata = langchain_store.get(ids=result["chunk_ids"])["metadatas"][0]
    assert metadata["doc_type"] == "benefits"
    assert metadata["department"] == "HR"
    assert metadata["doc_classification"] == "401k"
    cleanup()


async def test_apply_extracted_chunk_metadata_patches_chunks_after_first_index(monkeypatch):
    """Phase 19: the follow-up call pipeline.py makes once extraction
    finishes on a document's first index - every existing field (chunk_index,
    is_current, indexed_at) must survive the replace, not just the three new
    ones (same lesson as the supersede-flip test above)."""
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    result = await vector_indexer.write_chunks("doc-1", ["alpha", "beta"])

    await vector_indexer.apply_extracted_chunk_metadata(
        "doc-1",
        result["chunk_ids"],
        None,
        doc_type="benefits",
        department="HR",
        doc_classification="401k",
    )

    got = langchain_store.get(ids=result["chunk_ids"])
    for chunk_index, metadata in enumerate(got["metadatas"]):
        assert metadata["doc_type"] == "benefits"
        assert metadata["department"] == "HR"
        assert metadata["doc_classification"] == "401k"
        assert metadata["is_current"] is True
        assert metadata["document_id"] == "doc-1"
        assert metadata["chunk_index"] in (0, 1)
    cleanup()


async def test_apply_extracted_chunk_metadata_omits_fields_extraction_could_not_determine(monkeypatch):
    metadata_store, gateway, langchain_store, collection_name, record_manager_db, cleanup = _new_test_setup()
    _wire_test_doubles(monkeypatch, gateway, langchain_store, collection_name, record_manager_db)

    await metadata_store.create_document("doc-1", "policy.pdf", "data/uploads/doc-1/policy.pdf")
    result = await vector_indexer.write_chunks("doc-1", ["alpha"])

    await vector_indexer.apply_extracted_chunk_metadata(
        "doc-1", result["chunk_ids"], None, doc_type=None, department=None, doc_classification=None
    )

    metadata = langchain_store.get(ids=result["chunk_ids"])["metadatas"][0]
    assert "doc_type" not in metadata
    assert "department" not in metadata
    assert "doc_classification" not in metadata
    cleanup()
