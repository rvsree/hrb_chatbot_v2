"""Redis-backed answer cache (Phase 84) - exact-match only, keyed by a
hash of the query plus every retrieval/generation parameter that could
change the answer. Checked on every turn as of Phase 105, not just the
first message of a fresh conversation - the user explicitly chose speed
over per-turn context-freshness for a repeated exact-text question (see
pipeline.py's own wiring). Replaces the Postgres-backed version from
Phase 78 - same method signatures, so pipeline.py needed no changes for
that migration; only db_gateway.py's construction changed. clear_all() is
kept (SCAN+DELETE on a key prefix) for the same immediate-invalidation-
on-document-change behavior Phase 78 established - TTL is added on top as
defense in depth, not a replacement for it."""

import hashlib
import json

import redis.asyncio as redis

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("answer_cache")

KEY_PREFIX = "answer_cache:"
CONVO_TAG_PREFIX = "answer_cache_convo:"
DEFAULT_TTL_SECONDS = 60 * 60 * 6  # 6 hours - an answer can go stale when a document updates


def build_cache_key(query: str, **params) -> str:
    """Hashes the query plus every parameter that could change the answer -
    employee_id is never included, since a policy answer shouldn't vary by
    who asks. Unchanged from Phase 78."""
    canonical = json.dumps({"query": query, **params}, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AnswerCache:
    """Caches a full answer_query() result dict by its cache key."""

    PROVIDER_NAME = "redis"
    ENV_KEY = "REDIS_URL"

    def __init__(self, url: str | None = None):
        self.url = read_setting(url, "REDIS_URL")
        self.ttl_seconds = int(read_setting(None, "REDIS_ANSWER_CACHE_TTL_SECONDS", DEFAULT_TTL_SECONDS))

        if not self.url:
            logger.warning("[REDIS] REDIS_URL not set")

        self._client: redis.Redis | None = None

    def get_configuration(self) -> dict:
        # Never echo the URL itself - it carries the password.
        return {"configured": bool(self.url)}

    def _client_or_raise(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.url, decode_responses=True)
        return self._client

    async def get(self, cache_key: str) -> dict | None:
        """Returns None on a miss or if Redis is unreachable - never raises,
        so a down cache degrades to "no caching", not a broken request."""
        try:
            with log_backend_call(logger, "redis", "answer_cache.get", cache_key=cache_key):
                raw = await self._client_or_raise().get(KEY_PREFIX + cache_key)
                return json.loads(raw) if raw else None
        except Exception as error:
            logger.warning("[answer_cache] Redis unreachable on get, treating as a miss: %s", error)
            return None

    async def set(self, cache_key: str, query: str, answer: dict) -> None:
        """Best-effort - a failed cache write must never break the response that was already computed."""
        try:
            with log_backend_call(logger, "redis", "answer_cache.set", cache_key=cache_key):
                await self._client_or_raise().set(KEY_PREFIX + cache_key, json.dumps(answer), ex=self.ttl_seconds)
        except Exception as error:
            logger.warning("[answer_cache] Redis unreachable on set, skipping cache write: %s", error)

    async def tag_conversation(self, conversation_id: str, cache_key: str) -> None:
        """Phase 112: remembers that this conversation's history now
        depends on this cache entry, so deleting the conversation can
        purge it later - best-effort, same never-raise pattern as set()."""
        try:
            with log_backend_call(logger, "redis", "answer_cache.tag_conversation", conversation_id=conversation_id):
                client = self._client_or_raise()
                tag_key = CONVO_TAG_PREFIX + conversation_id
                await client.sadd(tag_key, cache_key)
                await client.expire(tag_key, self.ttl_seconds)
        except Exception as error:
            logger.warning("[answer_cache] Redis unreachable on tag_conversation, skipping: %s", error)

    async def clear_for_conversation(self, conversation_id: str) -> int:
        """Deletes every cache entry this conversation's own turns
        depended on - called when that conversation is deleted. A cache
        entry another conversation also relied on is removed for them
        too (accepted tradeoff - see RAG-ROADMAP.md Phase 112); their
        next identical question just regenerates it, same as any cold
        miss. Best-effort: a down cache just means those entries expire
        on their own TTL instead."""
        try:
            with log_backend_call(logger, "redis", "answer_cache.clear_for_conversation", conversation_id=conversation_id):
                client = self._client_or_raise()
                tag_key = CONVO_TAG_PREFIX + conversation_id
                cache_keys = await client.smembers(tag_key)
                deleted = 0
                for cache_key in cache_keys:
                    deleted += await client.delete(KEY_PREFIX + cache_key)
                await client.delete(tag_key)
                return deleted
        except Exception as error:
            logger.warning("[answer_cache] Redis unreachable on clear_for_conversation, skipping: %s", error)
            return 0

    async def clear_all(self) -> int:
        """Invalidation - clears every cached answer. Called whenever a document changes."""
        with log_backend_call(logger, "redis", "answer_cache.clear_all"):
            client = self._client_or_raise()
            deleted = 0
            async for key in client.scan_iter(match=KEY_PREFIX + "*"):
                deleted += await client.delete(key)
            return deleted

    async def health_check(self) -> dict:
        """Report whether this cache is usable - pings Redis, counts cached keys."""
        result = {"provider": self.PROVIDER_NAME}
        result.update(self.get_configuration())

        if not self.url:
            result["status"] = "unhealthy"
            result["message"] = "REDIS_URL not set"
            return result

        try:
            client = self._client_or_raise()
            await client.ping()
            count = 0
            async for _ in client.scan_iter(match=KEY_PREFIX + "*"):
                count += 1
            result["status"] = "healthy"
            result["answers_cached"] = count
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
