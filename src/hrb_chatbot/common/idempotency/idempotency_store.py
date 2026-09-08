"""In-memory idempotency-key support - retrying a POST with the same
Idempotency-Key header replays the cached response instead of re-running
the request (and, for the endpoints that spend money, re-spending it).

The convention this follows
-------------------------------
The same "Idempotency-Key" header name Stripe's API popularized: a client
generates one UUID per logical operation (not per HTTP attempt) and sends
it on every retry of that same operation. A network timeout, a dropped
connection right before the response arrives, or a client crash mid-
request all look identical to "did this actually happen?" from the
client's side - replaying the same key returns the same answer instead of
risking a duplicate document upload or a second embedding call for a
question that already got answered.

Same in-memory, single-process limitation as rate_limiter.py
-------------------------------------------------------------------
Resets on every restart/redeploy, and stops being correct the moment this
app runs as more than one instance - see that file's own docstring for
the full reasoning, which applies identically here.
"""

import time

# One hour - long enough to cover a real client's retry window (a few
# failed attempts over a slow connection) without keeping every response
# this process has ever produced in memory forever.
DEFAULT_TTL_SECONDS = 3600


class IdempotencyStore:
    """Caches one (status_code, response_body) per idempotency key, for a
    limited time."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        # {idempotency_key: (stored_at, status_code, response_body)}
        self._responses: dict[str, tuple[float, int, dict]] = {}

    def get(self, key: str) -> tuple[int, dict] | None:
        """Return the cached (status_code, response_body) for this key, or
        None if this key has never been seen or its entry expired."""
        entry = self._responses.get(key)
        if entry is None:
            return None

        stored_at, status_code, response_body = entry
        if time.time() - stored_at > self.ttl_seconds:
            del self._responses[key]
            return None

        return status_code, response_body

    def set(self, key: str, status_code: int, response_body: dict) -> None:
        """Record the response for this key, so a later replay of the same
        key returns it instead of re-running the request."""
        self._responses[key] = (time.time(), status_code, response_body)


# Same lazy-singleton pattern as ClientGateway/DBGateway/RateLimiter - one
# shared store for the whole process.
_shared_idempotency_store: IdempotencyStore | None = None


def get_idempotency_store() -> IdempotencyStore:
    """Return the one shared IdempotencyStore, creating it on the first call."""
    global _shared_idempotency_store
    if _shared_idempotency_store is None:
        _shared_idempotency_store = IdempotencyStore()
    return _shared_idempotency_store


def reset_idempotency_store() -> None:
    """Throw away the shared store so the next call builds a fresh one.
    Only needed in tests, same reasoning as reset_rate_limiter()."""
    global _shared_idempotency_store
    _shared_idempotency_store = None
