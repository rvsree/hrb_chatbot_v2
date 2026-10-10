"""Tests for ChromaDBClient.get_all_chunks() (Phase 131) - real embedded
ChromaDB against a pytest tmp_path, no network, matching this project's
existing real-but-isolated-backend testing convention."""

from src.hrb_chatbot.common.clients.db_client.chroma_client import ChromaDBClient


def _new_client(tmp_path):
    return ChromaDBClient(mode="persistent", persist_dir=str(tmp_path), collection_name="test_collection")


def test_get_all_chunks_returns_every_chunk_with_text_and_metadata(tmp_path):
    client = _new_client(tmp_path)
    client.upsert(
        "test_collection",
        ids=["chunk-1", "chunk-2"],
        documents=["first chunk text", "second chunk text"],
        embeddings=[[0.1, 0.2], [0.3, 0.4]],
        metadatas=[{"doc_id": "doc-1"}, {"doc_id": "doc-1"}],
    )

    chunks = client.get_all_chunks("test_collection")

    assert {chunk["id"] for chunk in chunks} == {"chunk-1", "chunk-2"}
    by_id = {chunk["id"]: chunk for chunk in chunks}
    assert by_id["chunk-1"]["text"] == "first chunk text"
    assert by_id["chunk-1"]["metadata"] == {"doc_id": "doc-1"}


def test_get_all_chunks_on_empty_collection_returns_empty_list(tmp_path):
    client = _new_client(tmp_path)
    client.get_collection("test_collection")  # creates it, still empty

    assert client.get_all_chunks("test_collection") == []
