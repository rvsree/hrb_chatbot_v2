"""Redis-backed embedding cache (Phase 84) - exact-match on
(content_hash, embedding_model), avoids re-embedding unchanged chunk text
on re-index. Ingestion-side only, same scope as Phase 77. Replaces the
Postgres-backed version - same method signatures, so
embedding_generator.py needed no changes at all; only db_gateway.py's
construction changed. Long TTL (an embedding for a given content hash
never changes, unlike an answer which can go stale)."""

import hashlib
import json

import redis.asyncio as redis

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.call_logger import log_backend_call
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("embedding_cache")

KEY_PREFIX = "embedding_cache:"
DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days - a given content hash's embedding never changes


def hash_text(text: str) -> str:
    """Same hashing approach documents_service.py already uses for
    document-level content_hash, applied at chunk granularity instead.
    Unchanged from Phase 77."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _redis_key(content_hash: str, embedding_model: str) -> str:
    return f"{KEY_PREFIX}{embedding_model}:{content_hash}"


class EmbeddingCache:
    """Caches embedding vectors by content hash + model."""

    PROVIDER_NAME = "redis"
    ENV_KEY = "REDIS_URL"

    def __init__(self, url: str | None = None):
        self.url = read_setting(url, "REDIS_URL")
        self.ttl_seconds = int(read_setting(None, "REDIS_EMBEDDING_CACHE_TTL_SECONDS", DEFAULT_TTL_SECONDS))

        if not self.url:
            logger.warning("[REDIS] REDIS_URL not set")

        self._client: redis.Redis | None = None

    def get_configuration(self) -> dict:
        return {"configured": bool(self.url)}

    def _client_or_raise(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.url, decode_responses=True)
        return self._client

    async def get_many(self, content_hashes: list[str], embedding_model: str) -> dict[str, list[float]]:
        """Returns {content_hash: embedding} for whichever of the given hashes
        are cached - missing hashes are simply absent. Never raises, even if
        Redis itself is unreachable: degrades to "embed everything", not a
        broken ingestion request."""
        if not content_hashes:
            return {}
        try:
            with log_backend_call(logger, "redis", "embedding_cache.get_many", count=len(content_hashes)):
                client = self._client_or_raise()
                keys = [_redis_key(content_hash, embedding_model) for content_hash in content_hashes]
                values = await client.mget(keys)
                return {
                    content_hash: json.loads(value)
                    for content_hash, value in zip(content_hashes, values, strict=True)
                    if value is not None
                }
        except Exception as error:
            logger.warning("[embedding_cache] Redis unreachable on get_many, treating as a full miss: %s", error)
            return {}

    async def set_many(self, entries: list[tuple[str, list[float]]], embedding_model: str) -> None:
        """Best-effort - a failed cache write must never break ingestion, the embeddings were already generated either way."""
        if not entries:
            return
        try:
            with log_backend_call(logger, "redis", "embedding_cache.set_many", count=len(entries)):
                client = self._client_or_raise()
                async with client.pipeline(transaction=False) as pipe:
                    for content_hash, embedding in entries:
                        pipe.set(_redis_key(content_hash, embedding_model), json.dumps(embedding), ex=self.ttl_seconds)
                    await pipe.execute()
        except Exception as error:
            logger.warning("[embedding_cache] Redis unreachable on set_many, skipping cache write: %s", error)

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
            result["entries_cached"] = count
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
