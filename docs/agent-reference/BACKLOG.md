# Backlog

Things identified while building the RAG boilerplate (2026-09-07) that are
real gaps but explicitly **not blocking** current work. Move an item out of
this file into `docs/agent-reference/RAG-ROADMAP.md`'s phase list when it's actually picked
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
  `docs/agent-reference/TESTING-GUIDE.md` for the A/B-comparison pattern that's the
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
  Phase 9 in `docs/agent-reference/RAG-ROADMAP.md` for the full account/permissions finding.
  `ask_with_tools()`'s tool-format conversion is still untested against a
  real tool call.
- **Tavily health check.** `common/clients/web_client/tavily_client.py`
  exists and is wired into `client_gateway.py`, but nothing calls its
  `health_check()` from `/health` - unlike the three LLM providers, it isn't
  an LLM so it doesn't belong under `check_llm()`. Needs its own
  `check_web_search()` (or similar) folded into `check_all_backend_services()`.

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
  - config-only, no rebuild. See Phase 10 in `docs/agent-reference/RAG-ROADMAP.md` for the
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

## CI/CD & branch strategy (2026-09-08) - see `docs/agent-reference/CICD-BRANCHING-STRATEGY.md`

- **pip-audit triage.** Wired into `ci.yml` as `continue-on-error: true` -
  report-only, not blocking. A real run turned up dozens of pre-existing
  CVEs across `langchain*`/`chromadb`/`starlette`/`pillow`, pinned for
  compatibility long before this scan existed. Needs someone to go
  through the list, upgrade what's safely upgradable (`chromadb` needs
  care - see the Python-3.13 fragility note in `README.md`'s
  Prerequisites), and explicitly accept-with-comment whatever can't move
  yet, before flipping this gate to blocking. See
  `docs/agent-reference/CICD-BRANCHING-STRATEGY.md`'s security-gate section for the exact
  steps.
- **No staging deployment target.** `develop` runs the full test gate but
  deploys nowhere - only `master` triggers `deploy.yml`, against the one
  existing App Runner service. Adding a second, always-on App Runner
  service for `develop` would give a real pre-prod environment, at the
  cost of a second continuous AWS bill. Deliberately not stood up without
  asking - see `docs/agent-reference/CICD-BRANCHING-STRATEGY.md`'s "Deployment targets"
  section for the two options laid out.
- **Docker images are tagged `:latest` only.** No way to redeploy a known-
  good previous image if a new one passes App Runner's own health check
  but is still broken in some way that check can't see - `:latest` is
  overwritten every deploy. Recommended fix: tag every build with
  `:${{ github.sha }}` too. Not implemented yet, deliberately - `deploy.yml`'s
  build command has caused three real, hard-to-diagnose failures before
  (see `AWS-DEVOPS-RUNBOOK.md`), so this needs its own isolated test
  before going anywhere near that line again.
- **GitHub repo settings not configured.** Default branch is still
  `hrb_rag_pipelines`, not `master` - a Settings → Branches action, not a
  `git push`. No branch protection rules exist either (nothing requires
  CI to pass, or a review, before a merge into `develop`/`master`).

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
- **Idempotency.** Done 2026-09-08, **removed 2026-09-13** - the
  `Idempotency-Key` header cache and the separate content-hash
  duplicate-upload check were both deliberately dropped (user decision,
  during the LangChain/LlamaIndex pipeline rewrite on
  `feature-langchain-rag-pipeline`) to simplify the request path while
  that rewrite is in progress. Back on the backlog as a real gap, not
  struck through - a real shared store (Redis) is the planned
  re-implementation once the pipeline rewrite is stable, see
  `docs/agent-reference/RAG-ROADMAP.md`'s phase entry.
- ~~**No app-level exception handler / possible info leak in error
  responses.**~~ Fixed 2026-09-08. An audit found two real `json_error(...)`
  calls that interpolated a caught exception's raw `str(error)` directly
  into the client-facing message
  (`routes_documents.py`'s index endpoint, `retrieve_document.py`'s query
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
  `docs/agent-reference/AWS-DEVOPS-RUNBOOK.md`). Add the same check there once Phase 6
  makes a real call.
- **Typed request/response/error contracts on every endpoint**, not just the
  ones built carefully - see `docs/agent-reference/CODING-STANDARDS.md` for the standard
  this is meant to hold to going forward. String fields on request models
  now also carry both a `min_length` and a `max_length` where the
  distinction matters (`RagQueryRequest.query`, `IndexRequest.vector_db`/
  `embedding_model`) - a structural, size-based guardrail, not the
  content-based (prompt-injection, PII) guardrails that remain Phase 7's
  hand-written work.

## Access control (Phase 23, 2026-09-15; identity mechanism replaced Phase 45, 2026-09-20)

- **Real OAuth still not built.** `api/gateway/rbac.py`'s `require_role()`
  reads a caller-supplied `user_profile` sub-object straight from the JSON
  request body (every endpoint, including `GET`/`DELETE`) as-is - a
  deliberate placeholder, trivially spoofable, not a security control
  (self-asserted in the same request it gates - see
  `docs/agent-reference/endpoint-request-response-contracts.md`).
  `common/clients/auth_client/oauth_client.py` is an empty placeholder for
  the real integration.
- ~~**Uploader identity isn't persisted.**~~ **Done, Phase 45:**
  `DocumentRecord`/`DocumentUploadResult` now carry `uploaded_by`
  (`documents_service.create_document()` threads the caller's
  `employee_id` through to a new DB column); `DocumentDeleteResponse`/
  `DocumentDeleteAllResponse` carry `deleted_by` the same way.
- **Rate limiting is still IP-keyed**, not by the identity the gateway now
  resolves - `common/rate_limiting/rate_limiter.py` predates Phase 23.
  Switching the key to `employee_id` (falling back to IP when absent)
  would rate-limit per person instead of per network address.
- **Retrieval is uniform across all three roles** - no per-document
  visibility differences (e.g. a manager-only document) - deferred per
  explicit request when this phase was scoped. Would build on the same
  chunk metadata (`doc_category`/`department`) Phase 19 already added.

## Dead code (Phase 22, found 2026-09-15 during comment cleanup)

- **`PineconeClient.query()`/`.upsert()` and `ChromaClient`'s equivalents
  look unused in the real pipeline.** Indexing (`vector_indexer.py`) and
  retrieval (`retriever.py`) both go through LangChain's own vector store
  objects (`langchain_vector_store.py`'s `get_vector_store()`) since Phase
  17/Phase 4 - confirmed by grepping the whole `src/` tree for any other
  caller of `.query(`/`.upsert(` and finding none. `delete()`/
  `update_metadata()` are still real (used directly by
  `documents_service.py`/`vector_indexer.py`'s supersede-flip), so this
  isn't the whole client, just these two methods (and their
  `BaseVectorDBClient` ABC requirement). Worth confirming and removing in
  a dedicated phase, not fixed here - this was noticed while trimming an
  unrelated docstring, not something this task set out to check.

## Retrieval quality (Phase 20, found 2026-09-14 during live verification)

- **Self-Query's `doc_description` filter only matches exact strings,
  but `doc_description` is deliberately free text** (Phase 19's own
  design - "not a fixed enum, real documents vary too much to hardcode a
  closed list"). Confirmed live: querying "what's my 401k vesting
  schedule" reliably makes Self-Query's LLM parse
  `doc_description="401k"` (it's the example in
  `ai/rag_pipeline/query_retrieval/retriever.py`'s own
  `METADATA_FIELD_INFO`), but a real indexed document's actual extracted
  value was `"401(k) Savings Plan"` - an exact-string mismatch that
  correctly-but-uselessly returns zero chunks, even though clearly
  relevant chunks exist. `doc_category` (extraction picks from a short fixed
  list: policy/regulatory/investment/benefits/other) doesn't have this
  problem - confirmed by isolating it, `doc_category=benefits` alone matched
  real chunks every time. Options for later: a `contain`/fuzzy comparator
  instead of `$eq` for `doc_description` specifically, or re-scoping it
  toward a smaller controlled set the way `doc_category` already is. See
  `docs/agent-reference/RAG-ROADMAP.md`'s Phase 20 entry for the full verification
  (field names there are historical - `doc_type`/`doc_classification`,
  renamed to `doc_category`/`doc_description` in Phase 57).

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

## Cleanup done 2026-09-21

- Removed `resources/db_scripts/` entirely (postgres/ and sqlite/, 13
  files) - described an unrelated, never-built project design (`coco`
  database, `chat_sessions`/`policy_versions`/`leave_rules`/`agent_tasks`/
  `user_feedback` tables, `src/app/common/db_scripts/...` paths that don't
  exist in this repo). Zero overlap with the real schema (`documents`/
  `chunks`, built via `CREATE TABLE IF NOT EXISTS` in `sqlite_client.py`/
  `postgres_client.py`) and zero references anywhere in `src/` or current
  docs - orphaned scaffolding from a different project, not this one's.
- Removed `README_TEST.md` - stale and factually wrong (old `/v1/rag/...`
  prefix, removed header-based auth from Phase 23, a "Phase 6 stub"
  reference long superseded). Fully replaced by `docs/agent-reference/TESTING-GUIDE.md`
  (pytest) and `postman/hrb_chatbot.postman_collection.json` (manual/
  curl-style testing), which the file's own last line already pointed to.
- Removed `postman/hrb_chatbot.postman_collection_v1.json` - a stale
  duplicate collection using a defunct `/index/v1/rag/documents` routing
  scheme, confusing to have alongside the real, actively-maintained
  collection.
- Removed `resources/kb_docs/text/indexing_batch_payload.json` - a sample
  payload for an API shape (`namespace`/`title`/`tags` fields) that was
  never this project's actual contract.
- Removed `src/hrb_chatbot/services/rag_service.py` - a literal one-line
  pass-through (`return await pipeline.answer_query(params)`) with no
  logic of its own, unlike `services/documents_service.py` (real logic:
  content-hash dedup, supersedes handling, file validation), which keeps
  its service layer. `api/rag/retrieve_document.py` now calls
  `ai/rag_pipeline/pipeline.py` directly - see `CLAUDE.md`'s architecture
  section for the updated request flow.
- **Not removed, flagged for the user's own call:** `infra/AgentCore
  Installation and Run Guide.md` (real forward-looking AWS Bedrock
  AgentCore deployment notes, not obviously stale) and
  `resources/kb_docs/text/*.txt` / `resources/kb_docs/word/*.docx`
  (real alternate-format copies of the 6 source PDFs, unreferenced by any
  code but plausibly intentional reference material, not junk like the
  payload JSON above).

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

## Guardrails / Evaluation / Observability follow-up (Phases 7-8, 2026-09-22)

- **3 of 6 KB documents not indexed.** 401(k), Unpaid TimeOff, and Sedgwick
  Unpaid Timeoff are missing from the vector store - leftover from the
  earlier live-DB-deletion incident, only 3 PDFs got re-uploaded
  afterward. Found via the DeepEval harness scoring 0.00 on a 401(k)
  question. Re-upload is simple, not done - your call on priority.
- **DeepEval CI gate not wired up.** The scoring harness
  (`golden_dataset_harness.py`) exists and is verified live; the actual
  PASS/REVIEW/BLOCK threshold job (`docs/agent-reference/CICD-BRANCHING-STRATEGY.md`'s
  practical-significance bar) isn't hooked into a CI workflow yet.
- **PII in a query gets blocked, not masked.** `self check input`'s LLM
  judgment flags SSN-like content before the dedicated `mask sensitive
  data on input` rail gets a turn (rails run in sequence). Defensible
  (safer), but different from "mask, don't block" - flagged for a
  decision if the stricter behavior isn't wanted.
- **Gate 2 (document-level ACL) and Gate 4 (context grading) still
  unbuilt.** Both explicitly out of scope for Phase 7 - real gaps in the
  six-gate framework, not started.
- **LangSmith stays off**, by design - re-enable (`.env`'s
  `LANGSMITH_ENABLED`) specifically when single/multi-agentic-rag work
  begins, per the agreed trace-budget cadence.

## MCP integration & cross-project schema standardization (2026-09-22)

- **`hrb_lms_mcp` integration done as a prototype - Phase 49.** Real,
  running FastMCP server, now actually called live from this project via
  `ai/rag_pipeline/tools/mcp_tools/`, manual keyword routing (not ReAct
  yet) in `pipeline.answer_query()`. See Phase 49 in this file for the
  full spec, the two real dependency bugs found (`mcp` version pin,
  `python-multipart` bump), and the live verification.
- **A third sibling project found**: `hrb_emp_assist`
  (`C:\workspace\poc\2026\hrb_emp_assist`) is the real "Status: Production"
  MCP client `hrb_lms_mcp`'s own README names as its primary consumer -
  Python/FastAPI, ReAct Multi-Agent, MCP Integration already built,
  version 2.0. This looks like the mature version of what `hrb_chatbot_v2`
  is a from-scratch educational rebuild of. Worth treating as a reference
  for "how was this actually built the first time" during future
  ReAct/agentic-rag phases, not just for schema comparison.
- **`hrb_emp_assist`'s missing DDL/DML *files* don't mean missing schema -
  corrected 2026-09-22 after actually querying the live Postgres server**,
  not just the file tree. `coco_schema_extensions.sql`/`coco_schema_dml.sql`/
  `coco_schema_missing_tables.sql`/`coco_schema_missing_tables_dml.sql`
  genuinely don't exist on disk anywhere in the project (confirmed via
  file search) - but the database objects they were meant to create
  **do exist and are live**: `disability_rules`, `retirement_rules`,
  `healthcare_rules`, `tuition_rules`, and the rest of the 9 "missing"
  tables are real tables in the `coco` Postgres database today. The real
  gap is narrower than first reported: those 9 tables are all at **0
  rows** - the DDL ran (or was run manually) at some point, the DML
  (the actual rules data) never landed, or was cleared. `hr_chatbot_schema_hitl.sql`
  (the 5th script) does exist on disk. Not touched - that project's own
  gap to close, flagged here only because it surfaced while checking.
- **The "shared database" design is not abandoned - it's live.** Corrected
  2026-09-22: the local Postgres server hosts 4 real databases -
  `hrb_chatbot_v2` (this project's own, 1 table), `hr_chatbot`, `coco`,
  and `postgres`. `hr_chatbot` has a `hrb_emp_lms` schema (61 employees -
  the 58 original plus the 3 this session added) and a `public` schema
  with real chat history (1,500 rows), sessions (109), HITL escalations
  (66) - `hrb_lms_mcp` and `hrb_emp_assist`/`hrb_copilot` are already
  sharing this one physical database today, split by schema, confirmed by
  querying it directly, not by reading a setup script's comments. Two
  more schemas found this way, undocumented anywhere read so far:
  `app_tracking` (mcp_server_registry/mcp_tools_registry/agent_registry/
  retry_queue - real MCP/agent observability tables, all empty) and
  `state_mngmt` (agent_entities/agent_ltm, has real data) - worth knowing
  about before designing this project's own future agent/memory work, to
  avoid reinventing a schema that already exists next door.
- **OAuth2 extended for app-to-app, alongside the existing human-to-app
  design** (`resources/db_scripts/oauth/oauth_schema_ddl.sql`): a new
  `client_scopes` table gives each `oauth_clients` row (a registered
  caller, not a person) a scoped allowlist - e.g. this project's own
  `hrb-lms-mcp-client` gets `mcp:get_leave_balance`/`mcp:get_leave_history`
  only, read-only until deliberately widened. `hrb_lms_mcp`'s own auth
  today is a single optional `X-API-Key` (not real OAuth2) - this table is
  this project's own record of who's allowed to call out, independent of
  how `hrb_lms_mcp` checks it on its side. Design only, not wired into
  actual token-issuing code yet, same status as the human-to-app half.
- **Known gap, not closed**: MCP-routed answers (Phase 49) skip the output
  guardrail (`check_output()`) - written for LLM-generated text, and
  running it would add a full extra LLM call to a path whose entire point
  is avoiding one. Worth a deliberate decision once real PII fields show
  up in an MCP tool's response, not assumed safe forever.
- **`ai/agents/` and `ai/rag_pipeline/tools/`** (both previously empty
  placeholders) - `tools/mcp_tools/` is no longer empty (Phase 49);
  `ai/agents/` still is, reserved for the actual ReAct orchestration that
  replaces Phase 49's keyword-matching stand-in.
- **Employee ID convention standardized to match `hrb_lms_mcp`'s real data**,
  2026-09-22: this project's `E00001`-style test identities (golden
  dataset era) are now `EMP0xx`/`MGR0xx`, matching `hrb_lms_mcp`'s real
  `employees` table exactly (`EMP001`-`EMP050`, `MGR001`-`MGR005`). Updated
  everywhere: `resources/db_scripts/oauth/*.sql`, 3 test files, Postman,
  README, `docs/agent-reference/endpoint-request-response-contracts.md`. Full suite still
  151 passing after the rename.
- **`hrb_lms_mcp`'s own sample data has an internal inconsistency** -
  3 test employees (`emp_12345`/`emp_67890`/`emp_11111`, lowercase,
  different shape) alongside the dominant `EMP0xx` convention, per that
  file's own comment tied to `tests/test_mcp_tools_integration.py`.
  Flagged, not touched - that project's own call, and the referencing test
  file wasn't verified safe to rename against.
- **A real cross-database FK limitation found while standardizing**: this
  project's OAuth sketch and `hrb_lms_mcp`'s employees table are different
  Postgres databases - a `manager_id` can't literally foreign-key across
  that boundary. `oauth_sample_data_dml.sql`'s new rows (`EMP051`/`EMP052`/
  `MGR006`, added to both projects' sample data for a shared identity)
  leave `manager_id` `NULL` here for that reason - only `hrb_lms_mcp`'s own
  copy of the same rows has a real, resolvable `manager_id`.
- **Superseded, 2026-09-22 (same day, later in the session)**: the note
  above about the shared-database direction "looking abandoned" was wrong
  and is now moot either way - see the next section. This project's own
  copies of `hr_chatbot_schema*.sql` are still deleted, but that no longer
  matters: Phase 50's OAuth2 schema and MCP registry both write directly
  into the real, live `hr_chatbot` database now, not a planned one.
- **Gate 2 (document ACL) plan sketched, not started** - see the six-gate
  framework note above; needs a decision on role-gated vs. department-gated
  document visibility before a spec is written.

## Schema/data work completed, 2026-09-22 (Phases 50-51 + OAuth2 redesign)

Five tasks, done in dependency order, each tested/verified live against
the real `hr_chatbot` Postgres database and the real `hrb_lms_mcp` server -
not simulated:

1. **DB model diagram** (`docs/dev-reference/db-model-overview.html`) - built first, to
   design against, then kept accurate to the final state below.
2. **OAuth2 schema redesigned** to reuse real data instead of duplicating
   it: new `hrb_chatbot_v2_auth` Postgres schema, living inside the
   shared `hr_chatbot` database (not a new database, not this project's
   own). `employee_roles.employee_id` is a real FK into
   `hrb_emp_lms.employees` - Postgres schemas in the same database CAN
   foreign-key across each other (unlike across separate databases, the
   real limitation found last time this was attempted). Applied for
   real: `EMP051`/`EMP052`/`MGR006` now have real roles
   (`hr_support`/`employee`/`manager`) in the live database, verified via
   a real join query, not just the SQL files on disk.
3. **MCP registry at startup (Phase 50)** - reuses `hr_chatbot.app_tracking`'s
   existing `mcp_server_registry`/`mcp_tools_registry`/`mcp_server_connections`
   tables (found already existing before this session, previously all
   empty - the exact pattern from the user's own v1 project,
   `hrb_emp_assist`). New `common/clients/db_client/mcp_registry_client.py`
   + `common/observability/mcp_registry_startup.py`, wired into `main.py`'s
   `lifespan`. Verified live: all 6 real `hrb_lms_mcp` tools registered on
   a real startup run. **Three real CHECK-constraint violations found and
   fixed live** (existing tables restrict `connection_type`/`status`/
   `connection_status` to fixed value lists not documented anywhere,
   only discoverable by inserting) - see Phase 50's detail in
   `docs/agent-reference/RAG-ROADMAP.md`.
4. **NFR-specific golden dataset (Phase 51)** -
   `resources/golden_dataset/nfr_golden_dataset.json` (14 cases: prompt
   injection, PII, jailbreak, toxic content, and 4 false-positive
   controls) + `ai/rag_pipeline/evaluations/nfr_golden_dataset_harness.py`,
   run live against the real `check_input()` guardrail. **Two real
   findings, not assumptions**: email/credit-card PII gets *masked*, not
   blocked, unlike SSN (dataset corrected to match verified behavior);
   and a genuine false-positive bug - `EMP052` gets misclassified as
   `<PERSON>` by Presidio's NER recognizer and masked. Kept as a
   documented `known_issue` in the dataset itself, not fixed (out of this
   task's scope) and not hidden by changing the expected outcome to match
   the bug.
5. **Main golden dataset (`golden_dataset.json`) checked, needs no
   update** - zero `employee_id`/identity references in it; it's purely
   query-to-answer pairs about document content, fully decoupled from who's
   asking. Confirmed by direct search, not assumed.

Full suite: 161 passed (2 new unit tests for the registry). Both
eval-marked harnesses (`pytest -m eval`): 2 passed live, including the
new NFR one, real LLM/guardrail calls both times.

**Follow-up, same day: all 3 foreign keys removed from `hrb_chatbot_v2_auth`**
(`employee_roles.employee_id` -> `hrb_emp_lms.employees`, `employee_roles.role_id`
-> `roles`, `client_scopes.client_id` -> `oauth_clients`) - user-directed,
real-world reasoning: a DB-enforced FK across schemas owned by different
services is the exact coupling the "shared database" pattern gets
criticized for (blocks independent migration/sharding, a schema change
on either side can silently break the other). Dropped live
(`ALTER TABLE ... DROP CONSTRAINT`, verified the app-level JOIN still
works identically), `oauth_schema_ddl.sql` updated to match, and
`docs/dev-reference/db-model-overview.html` updated with the reasoning. The 2 FKs
purely within this project's own schema were dropped too, for
consistency, not because they had the same coupling problem - simpler is
the better teaching example for a capstone project. **Not touched**: the
real FK on the shared `app_tracking.mcp_server_connections.server_id ->
mcp_server_registry.server_id` (Phase 50) - those tables are reused
infrastructure this project doesn't own, not this project's call to
redesign.

**Follow-up, same day: schema-per-service bounded-context isolation,
user-directed.** `hrb_chatbot_v2_auth` renamed to `hrb_chatbot_v2_core`
(a more accurate name - it's this project's own identity/RBAC data, not
just auth), and a new, deliberately empty `hrb_chatbot_v2_sessions`
schema created for future conversation/session-state tables - created
ahead of any table, not retrofitted after one lands somewhere less
isolated. Three bounded-context schemas in the one shared `hr_chatbot`
database: `hrb_chatbot_v2_core` (this project, identity),
`hrb_chatbot_v2_sessions` (this project, reserved for session state),
`hrb_emp_lms` (hrb_lms_mcp's own, untouched) - each schema owned by
exactly one service, matching DDD bounded-context conventions even while
physically sharing one Postgres instance. Applied live (`ALTER SCHEMA
RENAME`/`CREATE SCHEMA`), verified data/queries still work identically,
`oauth_schema_ddl.sql`/`oauth_sample_data_dml.sql`/`docs/dev-reference/db-model-overview.html`
all updated to match.

**Real finding while answering how the MCP auth key is configured**:
`hrb_lms_mcp`'s own `.env` has a real, non-empty `API_KEY` set, and its
README documents `X-API-Key` header auth as "optional, configurable" -
but the actual current source code has **zero enforcement of it
anywhere** (checked the whole `src/` tree; only a stale compiled `.pyc`
from an apparently-deleted `mcp_controller.py` still references the
header). The key is configured but dead - not wired into any request
path today. `hrb_chatbot_v2`'s own `HRB_LMS_MCP_API_KEY` is empty in
`.env`, so this project's real calls send no `X-API-Key` header at all,
which is why Phase 49/50's live calls worked without one. Not this
project's bug to fix (a different repo), flagged here since it's
directly relevant to "is this call actually authenticated" - it isn't.

**Superseded, same day (Phase 53): the dead X-API-Key gap above is
closed for real.** Real OAuth2 client-credentials now runs both sides -
`hrb_lms_mcp` issues and enforces signed JWTs (`POST /oauth/token`,
`BearerAuthMiddleware` on `/mcp`), `hrb_chatbot_v2` acquires and caches
one. Verified live both directions: no token -> real 401, wrong secret ->
real 401, valid credentials -> real signed JWT -> real authenticated
call succeeds. Full detail, including the two real repos' worth of new
files, in `docs/agent-reference/RAG-ROADMAP.md`'s Phase 53.

**Planned, not started: Phase 52, an analytics MCP server** for
aggregate/historical HR questions (leave-utilization trends, attrition,
benefits-cost trends) that Phase 49's per-employee tools can't answer -
researched (WebSearch) against real 2026 NL2SQL-MCP patterns from
Oracle/Microsoft/Google Cloud. Parking-lot spec only in
`docs/agent-reference/RAG-ROADMAP.md` - real spec work deferred until ReAct
orchestration exists to route to it, per the user's own sequencing.

## Conversation memory (Phase 58, 2026-09-25)

- **Move conversation history off in-process memory onto a real cache
  DB.** `ai/pre_processing/conversation_memory.py`'s `_CONVERSATIONS` dict
  is deliberately in-memory for now (user-directed: "in-memory for now,
  will plan to expand this to cache db later") - lost on every restart,
  and doesn't survive across multiple worker processes if this app is
  ever scaled beyond one. A real move (Redis or similar) would swap the
  module's internals only; `load_history()`/`save_turn()`/
  `new_conversation_id()`'s signatures are already the only thing
  `pipeline.py`/`orchestration_agent.py` depend on.
- **No API to list/inspect/clear a conversation's history.** A caller can
  only add to it via a query; nothing lets them see what's stored or
  reset it mid-conversation. Not asked for yet.
- **MCP-routed answers (leave balance/history) aren't added to
  conversation history**, even when `enable_conversation_memory` is on -
  `pipeline.py`'s `try_route_to_mcp()` early-return bypasses
  `generate_answer()` entirely, which is the only place a turn gets
  saved. A follow-up referencing an MCP-answered turn won't have it in
  context. See Phase 58's own spec in `docs/agent-reference/RAG-ROADMAP.md`.

## Process

- ~~**No test suite configured.**~~ Added 2026-09-08 - `pytest` +
  `pytest-asyncio` (`requirements-dev.txt`), 20 tests across chunking,
  embedding, indexing (the insert/update/stale-chunk-cleanup logic
  specifically, the highest-value case), the RAG query stub's contract,
  and a reference A/B-comparison pattern - see `docs/agent-reference/TESTING-GUIDE.md` for
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
- **Spec-Driven Development (SDD) adopted 2026-09-14** - see `CLAUDE.md`'s
  SDD section. Every phase picked up from here on needs a written, reviewed
  spec (a `Spec:` sub-list in its `docs/agent-reference/RAG-ROADMAP.md` bullet, via
  `/spec-new`) before implementation starts - this backlog is where planned
  work is tracked, but an item moving from here into an active phase should
  get a spec first, not go straight to code. No new `specs/`/`adr/` folder -
  everything lives in the existing `docs/agent-reference/RAG-ROADMAP.md`/`docs/agent-reference/FAQ.md`
  convention, plus new tooling under `.claude/` (skills, hooks, one
  `implementer` subagent).
- **Action item, deliberately not decided yet (2026-09-14): LangChain vs.
  LlamaIndex, which does what, going forward.** Surfaced while researching
  Phase 17 (moving indexing from LlamaIndex to LangChain's `index()`) -
  the common real-world pattern is actually the opposite split ("LlamaIndex
  for ingestion/indexing - its documented strength - LangChain for
  orchestration"), which cuts against Phase 17's direction. User has asked
  to revisit this later rather than resolve it now - Phase 17 proceeds as
  already spec'd in the meantime. Whoever picks this up next should read
  Phase 17's spec and its "not carried over" note in `CLAUDE.md` first.
