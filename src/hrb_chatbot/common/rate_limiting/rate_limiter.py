"""In-memory rate limiter - fixed window, one per client. Single-process
only; a real distributed store (Redis) is the fix once this runs as more than one instance."""

import time

from fastapi import HTTPException, Request

from src.hrb_chatbot.common.config.settings import read_setting
from src.hrb_chatbot.common.logging.logger import get_logger

logger = get_logger("rate_limiter")


def _setting_is_true(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes")


class RateLimiter:
    """Counts requests per client key in a fixed time window, and raises
    HTTPException(429) once a client exceeds the configured limit within
    the current window."""

    def __init__(
        self,
        enabled: str | None = None,
        max_requests: str | None = None,
        window_seconds: str | None = None,
    ):
        self.enabled = _setting_is_true(read_setting(enabled, "APP_RATE_LIMITING", "false"))
        self.max_requests = int(read_setting(max_requests, "APP_RATE_LIMIT_REQUESTS", "100"))
        self.window_seconds = int(read_setting(window_seconds, "APP_RATE_LIMIT_DURATION", "30"))

        # One entry per client key: (when this client's current window
        # started, how many requests they've made inside it).
        self._windows: dict[str, tuple[float, int]] = {}

    def check(self, client_key: str) -> None:
        """Record one request from client_key. Raises HTTPException(429) if
        this pushes them over the limit for the current window."""
        if not self.enabled:
            return

        now = time.time()
        window_start, count = self._windows.get(client_key, (now, 0))

        window_age = now - window_start
        if window_age >= self.window_seconds:
            # This client's previous window has fully elapsed - start a
            # fresh one rather than keep accumulating against a stale count.
            window_start = now
            count = 0

        count += 1
        self._windows[client_key] = (window_start, count)

        if count > self.max_requests:
            seconds_remaining_in_window = self.window_seconds - (now - window_start)
            retry_after_seconds = max(1, int(seconds_remaining_in_window))

            logger.warning(
                "[rate_limit] %s exceeded %d requests per %ds window",
                client_key,
                self.max_requests,
                self.window_seconds,
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {self.max_requests} requests per "
                    f"{self.window_seconds} seconds. Try again in {retry_after_seconds}s."
                ),
                headers={"Retry-After": str(retry_after_seconds)},
            )


# Same lazy-singleton pattern as ClientGateway/DBGateway - one shared
# limiter for the whole process.
_shared_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Return the one shared RateLimiter, creating it on the first call."""
    global _shared_rate_limiter
    if _shared_rate_limiter is None:
        _shared_rate_limiter = RateLimiter()
    return _shared_rate_limiter


def reset_rate_limiter() -> None:
    """Throw away the shared limiter so the next call builds a fresh one.

    Only needed in tests - same reasoning as reset_client_gateway()/reset_db_gateway().
    """
    global _shared_rate_limiter
    _shared_rate_limiter = None


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency - add `Depends(enforce_rate_limit)` to any route
    that should be rate-limited. Keys on the caller's IP, or "unknown" if request.client is unset."""
    if request.client:
        client_key = request.client.host
    else:
        client_key = "unknown"

    get_rate_limiter().check(client_key)
