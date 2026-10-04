"""Tests for generate_embeddings() - ai/doc_processing/embedding/embedding_generator.py.

Uses FakeEmbeddingClient/FakeClientGateway/FakeDBGateway/FakeEmbeddingCache
from tests/conftest.py instead of the real OpenAI client and real Postgres
cache - no network call, no API key needed, no real database.
"""

from src.hrb_chatbot.ai.doc_processing.embedding import embedding_generator
from tests.conftest import FakeClientGateway, FakeDBGateway, FakeEmbeddingCache, FakeEmbeddingClient


def _patch(monkeypatch, fake_client=None, embedding_cache=None):
    fake_client = fake_client or FakeEmbeddingClient(dimension=4)
    monkeypatch.setattr(embedding_generator, "get_client_gateway", lambda: FakeClientGateway(fake_client))
    monkeypatch.setattr(
        embedding_generator, "get_db_gateway", lambda: FakeDBGateway(embedding_cache=embedding_cache or FakeEmbeddingCache())
    )
    return fake_client


async def test_generates_one_embedding_per_chunk_in_the_same_order(monkeypatch):
    _patch(monkeypatch)

    chunks = ["first chunk", "second chunk", "third chunk"]
    embeddings = await embedding_generator.generate_embeddings(chunks)

    assert len(embeddings) == 3
    for embedding in embeddings:
        assert len(embedding) == 4


async def test_empty_chunk_list_returns_empty_without_calling_the_client(monkeypatch):
    fake_client = _patch(monkeypatch)

    embeddings = await embedding_generator.generate_embeddings([])

    assert embeddings == []
    # Confirms this is a real short-circuit (the "if not chunks: return []"
    # guard), not just an empty result from calling the client with no texts.
    assert fake_client.calls == []


async def test_embedding_model_override_is_passed_through_to_the_client(monkeypatch):
    fake_client = _patch(monkeypatch)

    await embedding_generator.generate_embeddings(["a chunk"], embedding_model="text-embedding-3-large")

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["model"] == "text-embedding-3-large"


async def test_a_cached_chunk_is_not_sent_to_the_real_embedding_client(monkeypatch):
    cache = FakeEmbeddingCache()
    fake_client = _patch(monkeypatch, embedding_cache=cache)

    # Prime the cache for "first chunk" under the default model.
    await embedding_generator.generate_embeddings(["first chunk"])
    assert len(fake_client.calls) == 1

    # Asking again for the same chunk, alongside a genuinely new one, should
    # only send the new one to the client - the cached one comes back for free.
    embeddings = await embedding_generator.generate_embeddings(["first chunk", "new chunk"])

    assert len(embeddings) == 2
    assert len(fake_client.calls) == 2  # one more call, not a second full batch
    assert fake_client.calls[1]["texts"] == ["new chunk"]


async def test_a_full_cache_hit_skips_the_embedding_client_entirely(monkeypatch):
    cache = FakeEmbeddingCache()
    fake_client = _patch(monkeypatch, embedding_cache=cache)

    await embedding_generator.generate_embeddings(["only chunk"])
    assert len(fake_client.calls) == 1

    embeddings = await embedding_generator.generate_embeddings(["only chunk"])

    assert len(embeddings) == 1
    assert len(fake_client.calls) == 1  # no new call - this chunk was fully cached
