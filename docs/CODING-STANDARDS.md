# Coding standards

Written down once here rather than repeated in every conversation about this
codebase. This describes what's already being followed as of Phase 1
(`common/clients/`, `api/admin/health_checks.py`) - not a new standard, a
record of the existing one so it holds for Phase 2 onward without drifting.

## Comments explain *why*, briefly

A comment earns its place by naming something a reader would otherwise get
wrong or be surprised by - a gotcha, a constraint, the reason a check exists.
It does not restate what the code already says by being well-named. Keep
them short - a line or two, not a paragraph - but don't strip the ones that
carry real information (see `chroma_client.py`'s note on why the client is
built lazily, or `settings.py`'s note on `.env` overriding the machine
environment).

## Errors: where they live depends on who reads them

Three different rules, by layer - the same distinction the sibling project
makes, and already visible in this codebase:

| Layer | Errors are | Because the reader is |
|---|---|---|
| A client (`common/clients/.../*.py`) | returned as data in a dict (`{"status": "unhealthy", "message": ...}`), never raised from `health_check()` | code that needs to report a reason, not crash - a health check that raises tells you nothing a stack trace didn't already ruin |
| A service (`services/*.py`, once they exist) | exceptions raised | a route handler, which needs to pick an HTTP status code |
| A route (`api/**/routes_*.py`) | a consistent JSON error shape | a person or client calling the API, who needs a code and a body they can act on |

`try`/`except` at the client layer catches broadly (`except Exception`) on
purpose in `health_check()` methods specifically, because a health endpoint
that itself crashes is strictly worse than one that reports "unhealthy: why".
Elsewhere, catch what you can actually handle - not everything.

## Every client follows the same shape

`BaseLLMClient` and `BaseVectorDBClient` are `ABC`s with a small, fixed set
of abstract methods. A new provider (LLM or database) implements all of
them or Python refuses to construct it - that's the safety net, not a
formality. `ask_with_tools` for LLMs always returns OpenAI's reply shape
regardless of provider; `upsert`/`query`/`delete` for vector stores always
take the same arguments regardless of backend. Calling code never has a
provider-specific branch outside the client itself.

## Health checks: two endpoints, not one endpoint with a toggle

`GET /ping` and `GET /health` are two separate endpoints with two separate
jobs, not one endpoint switched between a cheap and an expensive mode by a
`deep` query param (that toggle existed once and was removed - see
`docs/RAG-ROADMAP.md`/`docs/BACKLOG.md` for the history if it matters).

`GET /ping` never touches the network - it only confirms the process is up.
A container `HEALTHCHECK` or load balancer probe always points at `/ping` -
see the `Dockerfile` - because a probe firing every 30 seconds forever must
never be able to cost money or fail because some external backend is down.

`GET /health` always makes one real call per backend, and it's the cheapest
one that proves the connection actually works (`GET /models`,
`list_collections()`, never a chat completion or a paid query). If a
backend isn't configured or isn't reachable, `health_check()` reports that
as `{"status": "unhealthy", "message": "..."}` - it never raises (see
"Errors: where they live" above) - so a missing key surfaces as a clear
message in the response body, not a crash.

## API contracts: Pydantic models for business endpoints, dicts for health

**Business/data endpoints** (once they exist - `POST /rag/documents`,
`POST /rag/query`) declare a request model and a `response_model` - not a
bare dict FastAPI happens to serialize. This is what makes `/docs` actually
useful and catches a malformed request before a handler ever runs.

**Health/diagnostic endpoints are the deliberate exception** - `GET /health`
returns whatever `check_all_backend_services()` produces, wrapped by `health_response()`,
with no declared `response_model`. This matches the sibling project's own
convention, not a gap: what's being checked grows over time (an LLM check
today, a database check added this week, more later), and forcing that into
a fixed schema would mean editing a Pydantic model every time a check is
added, for a shape only a human debugging a key ever reads.

The error shape is consistent across endpoints either way - a single
`{"error": "...", ...extra}` convention (`json_error()` in
`api/dependencies.py`), not each router inventing its own.

Corrected 2026-09-07: this file previously claimed every endpoint uses a
`response_model`, which wasn't true even of the endpoints that existed at
the time - see `docs/BACKLOG.md` if this distinction ever needs revisiting.

## Logging

`common/logging/logger.py`'s `get_logger(name)` - stdlib `logging`, no
third-party dependency - is what every module imports. `common/logging/
log_helper.py` is a separate, still-unfinished thing (agent-message
tagging, not a logger factory) - see `docs/BACKLOG.md` if it's ever picked
back up. Log a warning when a setting is missing, an error when an
operation fails and the caller needs to know why - not routine successful
calls.

## Naming

Names read as English and are not abbreviated to save characters -
`check_database`, `get_client_gateway`, `sanitize_collection_name`. If a
name needs a comment to explain what it does (as opposed to why), the name
is wrong, not the comment.
