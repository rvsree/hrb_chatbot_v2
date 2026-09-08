# Backlog

Things identified while building the RAG boilerplate (2026-09-07) that are
real gaps but explicitly **not blocking** current work. Move an item out of
this file into `docs/RAG-ROADMAP.md`'s phase list when it's actually picked
up, rather than marking it done in place here.

## LLM providers

- ~~**Anthropic was unhealthy.**~~ Fixed 2026-09-07. Two independent bugs:
  `anthropic==0.40.0` (this project's original, unverified pin) has no
  `.models` attribute at all, confirmed by inspection - the deep health
  check always failed regardless of key validity. Bumped to `1.2.0`,
  matching the sibling project's working install. Separately, `.env`'s
  `ANTHROPIC_BASE_URL` carried an erroneous `/v1` suffix (Anthropic's own
  docstring says host-only, opposite of OpenAI) - corrected. Retested live:
  `healthy`, 11 models visible, `chat_model_available: true`.
- **Bedrock as an LLM provider.** Add `BedrockChatClient` implementing
  `BaseLLMClient`, alongside OpenAI/Anthropic/OpenRouter, using AWS's
  `bedrock-runtime` `Converse` API. Confirmed with the user: this is Bedrock
  *as one more provider option*, not adopting Bedrock AgentCore Runtime as
  the hosting platform (that's a materially different, bigger commitment -
  see `crewai_app_demo`'s `/ping` + `/invocations` contract if that's ever
  reconsidered).
- **Tavily health check.** `common/clients/web_client/tavily_client.py`
  exists and is wired into `client_gateway.py`, but nothing calls its
  `health_check()` from `/health` - unlike the three LLM providers, it isn't
  an LLM so it doesn't belong under `check_llm()`. Needs its own
  `check_web_search()` (or similar) folded into `check_everything()`.

## API hardening (same shape as the sibling project's NFR backlog)

- ~~**Upload constraints.**~~ Done in Phase 2 - PDF-only and 20MB-max
  validation in `services/documents_service.py`, verified with a real
  rejected file. Still no per-batch count limit (nothing stops a 500-file
  batch) - worth deciding if it ever matters at this project's scale.
- **Retry / circuit breaker.** No resilience exists for the OpenAI/Anthropic/
  OpenRouter calls or the ChromaDB calls. Same gap as the sibling project;
  same recommendation - a bounded, transient-failures-only retry at the
  client layer, a circuit breaker as a separate later decision.
- **Rate limiting / auth.** Nothing protects `POST /rag/query` once it
  exists - and unlike the read-only endpoints, every call to it spends
  tokens.
- **Versioning.** No `/v1` prefix anywhere.
- **Typed request/response/error contracts on every endpoint**, not just the
  ones built carefully - see `docs/CODING-STANDARDS.md` for the standard
  this is meant to hold to going forward.

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

- All eight `APP_*` settings (`APP_BASE_URL`, `APP_APP_NAME`,
  `APP_ENVIRONMENT`, `APP_DEBUG`, `APP_CSRF_PROTECTION`,
  `APP_RATE_LIMITING`, `APP_RATE_LIMIT_REQUESTS`,
  `APP_RATE_LIMIT_DURATION`) - already tracked above as "`app_settings.py` /
  `app_gateway.py` don't exist yet."
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

- **No test suite, linter, or formatter configured.** Deliberate for now
  given the learning-project priority, but worth a conscious decision before
  this grows much further - `crewai_app_demo` is the cautionary example of
  what "never got to it" looks like a year on.
- ~~**Dockerfile is unverified.**~~ Verified 2026-09-07, once Docker Desktop
  was actually running: build, run, and `HEALTHCHECK` all confirmed. Two
  real bugs were caught and fixed in the process, not just "it built":
  `python-magic-bin` (Windows-only) doesn't install on Linux - swapped for
  `python-magic` + `libmagic1` in the image; and `/srv` (and therefore the
  relative `data/` path ChromaDB/SQLite/uploads all write under) wasn't
  writable by the non-root container user - fixed by chowning `data/`
  specifically, not the whole image, before switching to that user.
