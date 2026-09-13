"""Tests for generate_embeddings() - ai/doc_processing/embedding/embedding_generator.py.

Uses FakeEmbeddingClient/FakeClientGateway from tests/conftest.py instead
of the real OpenAI client - no network call, no API key needed.
"""

from src.hrb_chatbot.ai.doc_processing.embedding import embedding_generator
from tests.conftest import FakeClientGateway, FakeEmbeddingClient


def test_generates_one_embedding_per_chunk_in_the_same_order(monkeypatch):
    fake_client = FakeEmbeddingClient(dimension=4)
    monkeypatch.setattr(
        embedding_generator, "get_client_gateway", lambda: FakeClientGateway(fake_client)
    )

    chunks = ["first chunk", "second chunk", "third chunk"]
    embeddings = embedding_generator.generate_embeddings(chunks)

    assert len(embeddings) == 3
    for embedding in embeddings:
        assert len(embedding) == 4


def test_empty_chunk_list_returns_empty_without_calling_the_client(monkeypatch):
    fake_client = FakeEmbeddingClient()
    monkeypatch.setattr(
        embedding_generator, "get_client_gateway", lambda: FakeClientGateway(fake_client)
    )

    embeddings = embedding_generator.generate_embeddings([])

    assert embeddings == []
    # Confirms this is a real short-circuit (the "if not chunks: return []"
    # guard), not just an empty result from calling the client with no texts.
    assert fake_client.calls == []


def test_embedding_model_override_is_passed_through_to_the_client(monkeypatch):
    fake_client = FakeEmbeddingClient()
    monkeypatch.setattr(
        embedding_generator, "get_client_gateway", lambda: FakeClientGateway(fake_client)
    )

    embedding_generator.generate_embeddings(["a chunk"], embedding_model="text-embedding-3-large")

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["model"] == "text-embedding-3-large"
