# Backlog

Things identified while building the RAG boilerplate (2026-09-07) that are
real gaps but explicitly **not blocking** current work. Move an item out of
this file into `docs/RAG-ROADMAP.md`'s phase list when it's actually picked
up, rather than marking it done in place here.

## Observability

- ~~**No logging around individual backend calls.**~~ Fixed 2026-09-08.
  Confirmed by direct audit that no client logged anything around its
  actual network call - only around a missing API key at construction time,
  or a whole pipeline step finishing. Added
  `common/logging/call_logger.py`'s `log_backend_call()` (a context
  manager - service, operation, duration_ms, status on every line) and
  wired it into all four LLM clients' `ask`/`ask_with_tools`/
  `get_embeddings`, both vector store clients' `upsert`/`query`/`delete`,
  and both metadata store clients' five methods. Verified live, not just
  by reading the code - a real index call now shows
  `[openai] embeddings.create succeeded in 2184.2ms - {'model': ...,
  'text_count': 45}` in the log, where before there was nothing at all
  between "starting to index" and "finished indexing." Deliberately not a
  LangSmith integration - structured consistently enough that swapping one
  in later means changing this one function's body, not every call site.
- **No correlation/request id across log lines.** A single `POST
  /rag/documents/{id}/index` call now produces several log lines (create,
  get, embeddings.create, upsert, set_chunk_ids, update_status - see
  above) but nothing ties them together as "one request" if two requests
  happen to interleave in the logs. Worth adding once this app sees real
  concurrent traffic; not worth it yet at single-user local/demo scale.
- **No retrieval-vs-generation latency breakdown yet** - can't exist until
  Phase 6 (real retrieval + generation) is built. The logging added above
  already reports per-call duration for every LLM and vector-store call
  individually (visible in the logs today), which is what a future
  retrieval-vs-generation metric would be built from - see
  `docs/TESTING-GUIDE.md` for the A/B-comparison pattern that's the
  natural next step once there's a real answer-quality metric to compare.

## LLM providers

- ~~**Anthropic was unhealthy.**~~ Fixed 2026-09-07. Two independent bugs:
  `anthropic==0.40.0` (this project's original, unverified pin) has no
  `.models` attribute at all, confirmed by inspection - the deep health
  check always failed regardless of key validity. Bumped to `1.2.0`,
  matching the sibling project's working install. Separately, `.env`'s
  `ANTHROPIC_BASE_URL` carried an erroneous `/v1` suffix (Anthropic's own
  docstring says host-only, opposite of OpenAI) - corrected. Retested live:
  `healthy`, 11 models visible, `chat_model_available: true`.
- ~~**Bedrock as an LLM provider.**~~ Done 2026-09-07 (Phase 9). `BedrockChatClient`
  implementing `BaseLLMClient` via the `Converse` API, wired into `/health`
  alongside OpenAI/Anthropic/OpenRouter. Confirmed with the user: Bedrock
  *as one more provider option*, not adopting Bedrock AgentCore Runtime as
  the hosting platform. One thing surfaced worth remembering: the deep
  health check passed using an ambient personal AWS credential already on
  this machine (`~/.aws/credentials`, identity `BedrockAgentCore`,
  account `418884736369`), not anything this project configured - see
  Phase 9 in `docs/RAG-ROADMAP.md` for the full account/permissions finding.
  `ask_with_tools()`'s tool-format conversion is still untested against a
  real tool call.
- **Tavily health check.** `common/clients/web_client/tavily_client.py`
  exists and is wired into `client_gateway.py`, but nothing calls its
  `health_check()` from `/health` - unlike the three LLM providers, it isn't
  an LLM so it doesn't belong under `check_llm()`. Needs its own
  `check_web_search()` (or similar) folded into `check_everything()`.

## AWS deployment (Phase 10, in progress)

- **Metadata store had no config switch - fixed.** `documents_service.py`,
  `vector_indexer.py`, and `routes_documents.py` all called
  `db_gateway.sqlite()` directly, hardcoded, unlike the vector store's
  `RAG_VECTOR_DB`. Surfaced by deploying to App Runner (no persistent
  local disk) rather than by reading the code. Added
  `db_gateway.metadata_store()` reading a new `RAG_METADATA_STORE` setting
  (`sqlite` default - local dev unchanged; `postgres` for anywhere without
  persistent disk) and switched all three call sites. Done 2026-09-07.
- **Deployed service is temporarily running `RAG_METADATA_STORE=sqlite`
  anyway** - the ephemeral option - because Neon (the chosen hosted
  Postgres) doesn't exist yet, and App Runner refuses to start a service
  whose `RuntimeEnvironmentSecrets` reference a not-yet-existing secret
  ARN. `RAG_VECTOR_DB=pinecone` is already live and persistent. Finish this
  once Neon exists: 5 more Secrets Manager entries
  (`hrb-chatbot/POSTGRES_DB_HOST/PORT/NAME/USER/PASSWORD`), then
  `apprunner.update_service` flipping the env var and adding those secrets
  - config-only, no rebuild. See Phase 10 in `docs/RAG-ROADMAP.md` for the
  exact resource ARNs.
- **AWS CLI upgrade stalled, not resolved.** `winget upgrade --id
  Amazon.AWSCLI` (2.0.30 → 2.36.40) got stuck at "Starting package
  install..." with no further progress - almost certainly a UAC elevation
  prompt this non-interactive shell can't answer. Doesn't block anything -
  deployment was scripted via `boto3` instead - but the CLI itself is still
  the old version. Needs a human to run the MSI installer directly and
  click through the UAC prompt.
- **Blocked on the user:** a free Neon Postgres project/database (neon.tech)
  - external signup, not something Claude Code can do on the user's behalf.

## API hardening (same shape as the sibling project's NFR backlog)

- ~~**Upload constraints.**~~ Done in Phase 2 - PDF-only and 20MB-max
  validation in `services/documents_service.py`, verified with a real
  rejected file. Still no per-batch count limit (nothing stops a 500-file
  batch) - worth deciding if it ever matters at this project's scale.
- **Retry / circuit breaker.** No resilience exists for the OpenAI/Anthropic/
  OpenRouter calls or the ChromaDB calls. Same gap as the sibling project;
  same recommendation - a bounded, transient-failures-only retry at the
  client layer, a circuit breaker as a separate later decision. **Not the
  same thing as rate limiting below** - retry/circuit-breaker is about
  *this app* handling a flaky backend gracefully; rate limiting is about
  protecting this app *from* too many callers.
- ~~**Rate limiting.**~~ Done 2026-09-08 -
  `common/rate_limiting/rate_limiter.py`, a fixed-window in-memory limiter
  applied via `Depends(enforce_rate_limit)` to every endpoint that writes
  state or spends money (upload, index, query). Finally gives
  `APP_RATE_LIMITING`/`APP_RATE_LIMIT_REQUESTS`/`APP_RATE_LIMIT_DURATION`
  a real job - they'd been sitting in `.env` unread since the first
  commit (see the "Orphan config" section below, now out of date on this
  point). Single-process, in-memory only - resets on redeploy, and would
  need a real shared store (Redis) the moment this app scales to more
  than one instance - documented in the module's own docstring, not a
  surprise to discover later.
- **Auth** - still nothing. Genuinely deferred, not overlooked: this is a
  single-user personal project today, and every other item on this list
  (rate limiting, idempotency, versioning) was worth doing without waiting
  for auth to exist first. Worth a real decision before this project ever
  has more than one real user.
- ~~**Versioning.**~~ Done 2026-09-08 - every business endpoint now lives
  under `/v1` (`main.py`'s `include_router(..., prefix="/v1")`).
  `GET /health` deliberately stays unversioned - a liveness/readiness
  probe needs one stable path regardless of API version, matching how
  AWS/Kubernetes health checks are conventionally exempted from an app's
  own versioning scheme.
- ~~**Idempotency.**~~ Done 2026-09-08 -
  `common/idempotency/idempotency_store.py`, an `Idempotency-Key` header
  (the same convention Stripe's API uses) on upload/index/query. Same
  single-process, in-memory limitation as rate limiting above.
- ~~**No app-level exception handler / possible info leak in error
  responses.**~~ Fixed 2026-09-08. An audit found two real `json_error(...)`
  calls that interpolated a caught exception's raw `str(error)` directly
  into the client-facing message
  (`routes_documents.py`'s index endpoint, `routes_query.py`'s query
  endpoint) - a genuine info-leak risk (a stack-trace fragment, an
  internal path, anything a library's own exception `__str__` happens to
  include). Both now log the full detail server-side and return a
  generic, safe message. `main.py` also gained a global
  `@app.exception_handler(Exception)` as a last-resort safety net for
  anything no individual route handler catches - confirmed by audit that
  none existed before this.
- ~~**No pre-flight backend-readiness check before spending money.**~~
  Fixed 2026-09-08 for the one endpoint that has a real backend
  dependency today - `index_document()` now checks (shallow, free -
  `deep=False`) that the LLM provider and vector store are at least
  configured *before* attempting the real chunk/embed/index call,
  returning a clean 503 instead of letting a config problem surface as a
  raw exception deep in the pipeline. **Deliberately not applied to the
  query endpoint yet** - it's still a pure stub with no real backend call
  to check readiness for, and gating it behind a real API key would break
  in CI, which runs with no secrets at all (see
  `docs/AWS-DEVOPS-RUNBOOK.md`). Add the same check there once Phase 6
  makes a real call.
- **Typed request/response/error contracts on every endpoint**, not just the
  ones built carefully - see `docs/CODING-STANDARDS.md` for the standard
  this is meant to hold to going forward. String fields on request models
  now also carry both a `min_length` and a `max_length` where the
  distinction matters (`RagQueryRequest.query`, `IndexRequest.vector_db`/
  `embedding_model`) - a structural, size-based guardrail, not the
  content-based (prompt-injection, PII) guardrails that remain Phase 7's
  hand-written work.

## Data handling

- **PII / sensitive data.** The knowledge base is real HR benefits
  documents. No conscious decision has been made yet about what's logged
  (query text? retrieved chunk contents?) or how long uploaded files and
  their embeddings are retained.
- **No `.env.example`.** Only a real `.env` exists in this repo - there's no
  template a new contributor (or a fresh clone) could copy and fill in
  without seeing real values. Worth creating one, redacted, the way the
  sibling project's `.env.example` documents every setting name with a
  comment on what reads it.

## Cleanup done 2026-09-07

- Removed 6 Microsoft Word lock files (`~$MC ....docx`, 162 bytes each,
  under `resources/kb_docs/word/`) - temp files Word creates while a
  document is open, never real content, should never have been committed.
- Removed `resources/postgres/` - a byte-for-byte duplicate of
  `resources/db_scripts/postgres/` (confirmed with `diff -rq`, zero
  differences). Kept the `db_scripts/postgres` copy, matching the sibling
  `db_scripts/sqlite/` naming already in use.

## Orphan config - flagged, not removed (touches `.env`, your call)

Checked every `.env` variable against the actual source - these are
declared but read by nothing:

- `APP_BASE_URL`, `APP_APP_NAME`, `APP_ENVIRONMENT`, `APP_DEBUG`,
  `APP_CSRF_PROTECTION` - still orphaned, tracked above as
  "`app_settings.py`/`app_gateway.py` don't exist yet."
- ~~`APP_RATE_LIMITING`, `APP_RATE_LIMIT_REQUESTS`,
  `APP_RATE_LIMIT_DURATION`~~ - no longer orphaned as of 2026-09-08, now
  read by `common/rate_limiting/rate_limiter.py` - see the "Rate limiting"
  entry above.
- `OPENAI_RAG_MODEL` - not read anywhere; only `OPENAI_CHAT_MODEL` and
  `OPENAI_EMBED_MODEL` are.
- `ANTHROPIC_LLM_ENABLED` - not read anywhere; nothing gates on it.
- `TAVILY_SEARCH_ENABLED`, `TAVILY_MAX_RESULTS`, `TAVILY_SEARCH_DEPTH`,
  `TAVILY_INCLUDE_ANSWER` - `TavilyClient.search()` takes these as function
  parameters with hardcoded defaults, not as env-driven settings, so these
  four `.env` lines currently do nothing.

Also noted, not touched: `common/logging/log_helper.py` still has its own
broken import (`agent_log_tags` module doesn't exist) - this was an
explicit earlier decision to keep as-is for later, not a new finding.

## Process

- ~~**No test suite configured.**~~ Added 2026-09-08 - `pytest` +
  `pytest-asyncio` (`requirements-dev.txt`), 20 tests across chunking,
  embedding, indexing (the insert/update/stale-chunk-cleanup logic
  specifically, the highest-value case), the RAG query stub's contract,
  and a reference A/B-comparison pattern - see `docs/TESTING-GUIDE.md` for
  what's covered and why, and the fake-based pattern
  (`tests/conftest.py`) to extend once the hand-written pipeline exists.
  **Linter/formatter still not configured** - `ruff` is set up for the
  sibling `w1_agentic_foundations` project but not this one; still worth a
  conscious decision, same "don't let this become `crewai_app_demo`"
  reasoning as before.
- ~~**Dockerfile is unverified.**~~ Verified 2026-09-07, once Docker Desktop
  was actually running: build, run, and `HEALTHCHECK` all confirmed. Two
  real bugs were caught and fixed in the process, not just "it built":
  `python-magic-bin` (Windows-only) doesn't install on Linux - swapped for
  `python-magic` + `libmagic1` in the image; and `/srv` (and therefore the
  relative `data/` path ChromaDB/SQLite/uploads all write under) wasn't
  writable by the non-root container user - fixed by chowning `data/`
  specifically, not the whole image, before switching to that user.
