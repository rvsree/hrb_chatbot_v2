"""Phase 112: tag_conversation()/clear_for_conversation() - no real Redis,
_client_or_raise() faked with a minimal in-memory stand-in covering just
the Redis commands these two methods use."""

from src.hrb_chatbot.common.clients.cache_client.answer_cache import AnswerCache


class _FakeRedisClient:
    def __init__(self):
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    async def get(self, key):
        return self.strings.get(key)

    async def set(self, key, value, ex=None):
        self.strings[key] = value

    async def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    async def expire(self, key, seconds):
        pass

    async def smembers(self, key):
        return set(self.sets.get(key, set()))

    async def delete(self, key):
        deleted = 0
        if self.strings.pop(key, None) is not None:
            deleted += 1
        if self.sets.pop(key, None) is not None:
            deleted += 1
        return deleted


def _store_with_fake_redis(monkeypatch):
    cache = AnswerCache(url="redis://fake")
    fake_client = _FakeRedisClient()
    monkeypatch.setattr(cache, "_client_or_raise", lambda: fake_client)
    return cache, fake_client


async def test_tag_then_clear_deletes_the_tagged_entry(monkeypatch):
    cache, fake_client = _store_with_fake_redis(monkeypatch)
    await cache.set("key-1", "what is the pto policy?", {"answer": "x"})
    await cache.tag_conversation("conv-1", "key-1")

    deleted = await cache.clear_for_conversation("conv-1")

    assert deleted == 1
    assert await cache.get("key-1") is None


async def test_clearing_one_conversation_does_not_touch_another_entry(monkeypatch):
    cache, fake_client = _store_with_fake_redis(monkeypatch)
    await cache.set("key-1", "q1", {"answer": "x"})
    await cache.set("key-2", "q2", {"answer": "y"})
    await cache.tag_conversation("conv-1", "key-1")
    await cache.tag_conversation("conv-2", "key-2")

    await cache.clear_for_conversation("conv-1")

    assert await cache.get("key-1") is None
    assert (await cache.get("key-2"))["answer"] == "y"


async def test_clearing_an_untagged_conversation_deletes_nothing(monkeypatch):
    cache, fake_client = _store_with_fake_redis(monkeypatch)
    await cache.set("key-1", "q1", {"answer": "x"})

    deleted = await cache.clear_for_conversation("never-tagged")

    assert deleted == 0
    assert (await cache.get("key-1"))["answer"] == "x"


async def test_two_conversations_sharing_one_cache_entry_both_tag_it(monkeypatch):
    """Matches build_cache_key()'s own design - no employee_id in the key,
    so two different conversations asking the identical question share
    one entry. Deleting either one still removes it (the accepted
    tradeoff documented in RAG-ROADMAP.md's Phase 112 entry)."""
    cache, fake_client = _store_with_fake_redis(monkeypatch)
    await cache.set("shared-key", "same question", {"answer": "x"})
    await cache.tag_conversation("conv-a", "shared-key")
    await cache.tag_conversation("conv-b", "shared-key")

    deleted = await cache.clear_for_conversation("conv-a")

    assert deleted == 1
    assert await cache.get("shared-key") is None
