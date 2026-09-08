"""Logs the start, duration, and outcome of one outbound call to a backend
service (an LLM provider, a vector store, a metadata store) - not what the
app does with the result, just that the call happened, how long it took,
and whether it succeeded.

Why this exists
----------------
An audit of every client file in common/clients/ found logging only in two
places: a warning when an API key is missing (at client construction, not
call time), and a summary log after a whole pipeline step finishes. The
actual network call in between - the OpenAI completion, the Pinecone
query, the SQLite write - was invisible: nothing recorded when it started,
how long it took, or that it failed, only that something further upstream
eventually failed too. `log_backend_call` fixes that in one place instead
of separately in every client file.

Every log line carries the same fields (service, operation, duration_ms,
status) specifically so a future switch to LangSmith (or any other tracing
tool) has a consistent shape to migrate from - this file is deliberately
NOT a LangSmith integration itself, just structured enough that wiring one
in later means changing this one function's body, not every call site that
uses it.

Why a context manager ("with ... :"), for anyone coming from Java
------------------------------------------------------------------
Java's closest equivalent is try-with-resources (`try (var x = ...) { }`):
code that must run no matter how the block inside it exits - success,
return, or exception - written once instead of duplicated into every
try/except/finally at every call site. Here, that "must always run" code
is "log how long this took and whether it worked."
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from logging import Logger


@contextmanager
def log_backend_call(logger: Logger, service: str, operation: str, **context) -> Iterator[None]:
    """Wrap one outbound call to a backend service with a start/end log.

    Usage:
        with log_backend_call(logger, "openai", "chat.ask", model=self.model):
            response = self.client.chat.completions.create(...)

    `service` is the backend being called ("openai", "pinecone", "sqlite",
    ...). `operation` is what's being asked of it ("chat.ask",
    "vector.upsert", "metadata.get_document", ...). Any extra keyword
    arguments are logged alongside them as context - pass things like a
    model name or a row count, never the actual prompt/document text or a
    secret value, since these lines are meant to be safe to read in any log
    aggregator.
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
