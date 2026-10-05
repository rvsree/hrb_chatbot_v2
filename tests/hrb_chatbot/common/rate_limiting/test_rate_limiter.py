"""Tests for RateLimiter - common/rate_limiting/rate_limiter.py (Phase 84,
Redis-backed). A minimal FakeRedisClient stands in for redis.asyncio.Redis -
only incr/expire/ttl, the 3 methods RateLimiter actually calls - same
no-real-network-call convention as every other test in this project, no
new library (fakeredis) needed for 3 methods.
"""

import pytest
from fastapi import HTTPException

from src.hrb_chatbot.common.rate_limiting.rate_limiter import RateLimiter


class FakeRedisClient:
    def __init__(self):
        self._counts: dict[str, int] = {}
        self._ttls: dict[str, int] = {}

    async def incr(self, key):
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key, seconds):
        self._ttls[key] = seconds

    async def ttl(self, key):
        return self._ttls.get(key, -1)


def _limiter(**kwargs) -> RateLimiter:
    limiter = RateLimiter(redis_url="redis://fake", **kwargs)
    limiter._client = FakeRedisClient()
    return limiter


async def test_disabled_limiter_never_raises_regardless_of_request_count():
    limiter = _limiter(enabled="false", max_requests="2", window_seconds="60")

    for _ in range(10):
        await limiter.check("client-a")  # would raise well before 10 if enabled


async def test_enabled_limiter_allows_requests_up_to_the_limit():
    limiter = _limiter(enabled="true", max_requests="3", window_seconds="60")

    await limiter.check("client-a")
    await limiter.check("client-a")
    await limiter.check("client-a")  # exactly at the limit - still allowed


async def test_enabled_limiter_rejects_the_request_that_exceeds_the_limit():
    limiter = _limiter(enabled="true", max_requests="2", window_seconds="60")

    await limiter.check("client-a")
    await limiter.check("client-a")

    with pytest.raises(HTTPException) as exc_info:
        await limiter.check("client-a")

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


async def test_different_clients_have_independent_limits():
    limiter = _limiter(enabled="true", max_requests="1", window_seconds="60")

    await limiter.check("client-a")
    await limiter.check("client-b")  # client-a's count must not count against client-b

    with pytest.raises(HTTPException):
        await limiter.check("client-a")  # client-a's own second request still rejected
