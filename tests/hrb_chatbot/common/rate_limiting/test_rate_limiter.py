"""Tests for RateLimiter - common/rate_limiting/rate_limiter.py.

No FastAPI/TestClient here - RateLimiter's check() method is plain Python,
testable directly without going through a real HTTP request.
"""

import pytest
from fastapi import HTTPException

from src.hrb_chatbot.common.rate_limiting.rate_limiter import RateLimiter


def test_disabled_limiter_never_raises_regardless_of_request_count():
    limiter = RateLimiter(enabled="false", max_requests="2", window_seconds="60")

    for _ in range(10):
        limiter.check("client-a")  # would raise well before 10 if enabled


def test_enabled_limiter_allows_requests_up_to_the_limit():
    limiter = RateLimiter(enabled="true", max_requests="3", window_seconds="60")

    limiter.check("client-a")
    limiter.check("client-a")
    limiter.check("client-a")  # exactly at the limit - still allowed


def test_enabled_limiter_rejects_the_request_that_exceeds_the_limit():
    limiter = RateLimiter(enabled="true", max_requests="2", window_seconds="60")

    limiter.check("client-a")
    limiter.check("client-a")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("client-a")

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_different_clients_have_independent_limits():
    limiter = RateLimiter(enabled="true", max_requests="1", window_seconds="60")

    limiter.check("client-a")
    limiter.check("client-b")  # client-a's count must not count against client-b

    with pytest.raises(HTTPException):
        limiter.check("client-a")  # client-a's own second request still rejected
