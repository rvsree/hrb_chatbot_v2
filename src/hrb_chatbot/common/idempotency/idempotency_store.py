"""In-memory idempotency-key support - retrying a POST with the same
Idempotency-Key header replays the cached response instead of re-running
the request. Same "Idempotency-Key" convention Stripe's API popularized.

Same in-memory, single-process limitation as rate_limiter.py - see that
file's docstring for the full reasoning.
"""

import time

# One hour - long enough for a real retry window without keeping every
# response in memory forever.
DEFAULT_TTL_SECONDS = 3600


class IdempotencyStore:
    """Caches one (status_code, response_body) per idempotency key, for a
    limited time."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

        # A dict, like Java's Map<String, ...>. The value is a tuple - Python's
        # lightweight stand-in for a small DTO when defining a whole class
        # feels like overkill: (when this was cached, the status code, the
        # response body). Unpacked back into three named variables in get()
        # below, the same data either way.
        self._responses: dict[str, tuple[float, int, dict]] = {}

    def get(self, key: str) -> tuple[int, dict] | None:
        """Return the cached (status_code, response_body) for this key.
        Returns None if this key was never seen, or its entry expired."""
        entry = self._responses.get(key)
        if entry is None:
            return None

        # Unpack the 3-item tuple into three names in one line - equivalent
        # to reading entry.storedAt()/entry.statusCode()/entry.responseBody()
        # off a small Java record, just without declaring the record type.
        stored_at, status_code, response_body = entry
        if time.time() - stored_at > self.ttl_seconds:
            del self._responses[key]  # del removes a dict entry - like Map.remove(key).
            return None

        return status_code, response_body

    def set(self, key: str, status_code: int, response_body: dict) -> None:
        """Record the response for this key, so a later replay of the same
        key returns it instead of re-running the request."""
        self._responses[key] = (time.time(), status_code, response_body)


# Singleton, Python-style: no DI container/@Component here like Spring's
# ApplicationContext - this module-level variable IS the one shared instance,
# and `global` (below) lets a function reassign it instead of creating a new
# local variable. See client_gateway.py's _shared_gateway for the same
# pattern spelled out in more detail; every store/gateway/limiter in this
# project follows it.
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
