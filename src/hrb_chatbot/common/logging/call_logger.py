"""Logs the start/duration/outcome of one outbound backend call (LLM, vector
store, metadata store) - a context manager so this lives here once, not per call site."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from logging import Logger


@contextmanager
def log_backend_call(logger: Logger, service: str, operation: str, **context) -> Iterator[None]:
    """Wrap one outbound call to a backend service with a start/end log.

    Extra kwargs are logged as context - never pass secrets or raw prompt/document text.
    """
    started_at = time.perf_counter()

    try:
        yield
    except Exception as error:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
        logger.error(
            "[%s] %s failed after %sms (%s): %s",
            service,
            operation,
            duration_ms,
            type(error).__name__,
            error,
            extra={"service": service, "operation": operation, "duration_ms": duration_ms, "status": "error"},
        )
        raise
    else:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
        logger.info(
            "[%s] %s succeeded in %sms - %s",
            service,
            operation,
            duration_ms,
            context,
            extra={"service": service, "operation": operation, "duration_ms": duration_ms, "status": "success"},
        )
