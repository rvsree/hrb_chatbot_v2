# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An HR benefits chatbot backed by a RAG pipeline over the JPMC benefits knowledge base (`resources/kb_docs/`). Being built by hand, one feature at a time, to apply RAG concepts from the Interview Kickstart FDE cohort. **[docs/RAG-ROADMAP.md](docs/RAG-ROADMAP.md) is the source of truth for what's actually done** - phase-by-phase history, not aspirational. [docs/BACKLOG.md](docs/BACKLOG.md) lists known gaps and planned work; don't assume something is missing/broken without checking there first.

FastAPI backend, Python 3.12 only (not 3.13/3.14 - `chromadb` depends on removed Pydantic v1 internals). Everything imports as `from src.hrb_chatbot....` - `src/__init__.py` exists on purpose, always run as a module from the repo root, never from inside `src/`.

## Commands

```powershell
# install
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

# run (local dev)
.venv\Scripts\python.exe -m uvicorn src.hrb_chatbot.main:app --reload --port 8093

# full test suite
.venv\Scripts\python.exe -m pytest -v

# single test file / single test
.venv\Scripts\python.exe -m pytest tests/hrb_chatbot/api/rag/test_routes_documents.py -v
.venv\Scripts\python.exe -m pytest tests/hrb_chatbot/api/rag/test_routes_documents.py::test_name -v

# with coverage (CI enforces --cov-fail-under=45, a ratchet floor, not a target)
.venv\Scripts\python.exe -m pytest -v --cov=src/hrb_chatbot --cov-report=term-missing --cov-fail-under=45

# security gates CI runs (bandit blocks on MEDIUM+, pip-audit is report-only)
bandit -r src/hrb_chatbot -ll
pip-audit -r requirements.txt

# docker
docker buildx build --provenance=false --sbom=false --output type=docker -t hrb-chatbot:local .
docker run --rm --env-file .env -p 8093:8093 hrb-chatbot:local
```

No test needs a real API key, network call, or costs money - `tests/conftest.py`'s fakes match every real client's method signature exactly, so tests run identically with or without `.env` configured. `pytest.ini` sets `asyncio_mode = auto`, so `async def test_...` needs no `@pytest.mark.asyncio` decorator. Test files mirror `src/` paths 1:1 (e.g. `src/hrb_chatbot/ai/doc_processing/chunking/text_chunker.py` -> `tests/hrb_chatbot/ai/doc_processing/chunking/test_text_chunker.py`).

`git config core.hooksPath .githooks` (not on by default) enables a pre-commit hook that blocks committing anything matching a real API key pattern.

## Architecture

### Request flow

`main.py` (FastAPI app + global exception handlers) -> **gateway** (`api/gateway/`, Phase 23 - role-based access, wired as `dependencies=[...]` at `app.include_router(...)` level, not inside individual routes) -> `api/**/routes_*.py` (routers, one per resource, Pydantic request/response models only - see `models/`) -> `services/*.py` (thin orchestration layer, exists so routers never import `ai/` directly) -> `ai/**/pipeline.py` (the actual RAG logic) -> `common/clients/**` (one class per external backend, behind a gateway).

There are **two separate pipelines** under `ai/`, easy to confuse by name:
- `ai/doc_processing/pipeline.py` - **ingestion**: extract PDF text -> chunk -> embed -> index. Driven by `POST /v1/rag-ingestion/documents/{id}/index`. Gateway-restricted to `HR_SUPPORT` only.
- `ai/rag_pipeline/pipeline.py` - **query**: decompose -> retrieve -> generate. Driven by `POST /v1/rag-retrieval/query`. Gateway-open to `EMPLOYEE`/`MANAGER`/`HR_SUPPORT`, uniformly.

**Gateway identity is a placeholder, not real auth** - `api/gateway/current_user.py` reads three unsigned request headers (`X-Employee-Id`/`X-Full-Name`/`X-Role`) as-is; real OAuth is deferred (empty placeholder: `common/clients/auth_client/oauth_client.py`), and only `get_current_user()`'s internals need to change when it lands - `api/gateway/rbac.py`'s `require_role()` and every route stay untouched.

`ai/agents/`, `ai/pre_processing/` (guardrails, query decomposition, search filtering), `ai/rag_pipeline/helper/access_control.py`, `ai/rag_pipeline/tools/`, and `common/observability/` are empty placeholder files (0 bytes) - scaffolding for future phases per the roadmap, not dead code to clean up.

### Three different libraries, one per pipeline stage, deliberately

This mirrored the workshop's own module structure originally - not an
accident. **Indexing moved off LlamaIndex onto LangChain in Phase 17**
(2026-09-14) - a deliberate, recorded exception, not a quiet drift; see
`docs/FAQ.md`'s "Why indexing moved off LlamaIndex" entry for the real
reason (LangChain's `index()` gives real skip-if-unchanged + cleanup for
free) and the honest tradeoff it accepted. Don't further "consolidate"
chunking or retrieval onto a different library without the same kind of
recorded reason:
- **Chunking** (`ai/doc_processing/chunking/text_chunker.py`) - LangChain's own splitters, 6 selectable strategies via a `CHUNKING_STRATEGIES` dict (name -> function), auto-selected by `decide_chunking_strategy()` when not given explicitly.
- **Indexing** (`ai/doc_processing/indexing/vector_indexer.py`) - LangChain's own `index()` + `SQLRecordManager` (Phase 17) for the actual vector write, via the shared builder in `common/clients/db_client/langchain_vector_store.py`; everything around it (which document supersedes which, `is_current` flips) stays this project's own logic - `SQLRecordManager` has no concept of one document replacing a different one.
- **Search/retrieval** (`ai/rag_pipeline/query_retrieval/retriever.py`) - raw LangChain (`langchain_chroma`/`langchain_pinecone`), two plain functions (similarity, MMR) via a `SEARCH_STRATEGIES` dict, no classes - matches the workshop demo's own style. Phase 20 layers LangChain's own `MultiQueryRetriever`/`SelfQueryRetriever` classes on top of either (`RagQueryRequest.use_multi_query`/`use_self_query`) - these two are genuine LangChain classes, not hand-written, since the retrieval-rewriting/filter-parsing logic they implement isn't something this project's own code needs to reinvent. Both need a real LangChain `BaseChatModel`; see `common/clients/llm_client/langchain_chat_model.py`'s `GatewayChatModel` (a small adapter over this project's own multi-provider `ask()` clients, not one of LangChain's own per-provider packages - `docs/RAG-ROADMAP.md`'s Phase 20 entry has the real dependency conflict that ruled those out).

### Backend abstraction: gateways + enums, not scattered if/elif

Every external backend (LLM provider, vector store, metadata store) has a `Base*Client` ABC (`common/clients/*/base_*.py`) that every concrete client implements identically, and a singleton `*Gateway` (`client_gateway.py`, `db_gateway.py`) that builds each client lazily and caches it. Calling code never branches on provider outside the gateway. Which provider to use is a `src/hrb_chatbot/common/enums.py` `StrEnum` (`VectorDB`, `MetadataStore`, `LlmProvider`) everywhere it's a request parameter (Pydantic model field or FastAPI `Query`) - this is what makes an unknown provider name a clean 422 at the API boundary instead of silently falling through to a default or failing deep in the pipeline. Free-text fields that are genuinely open-ended (model names like `gpt-4.1-mini`) stay plain `str`, not enums.

### Health checks: two endpoints, not a toggle

`GET /ping` - process-is-up only, no provider calls, instant. This is what Docker's `HEALTHCHECK` and the CI deploy smoke test point at. `GET /health` - always makes one real (but free) call per backend and reports `{"status": "healthy"|"unhealthy", "message": "..."}`; `health_check()` never raises. See [docs/CODING-STANDARDS.md](docs/CODING-STANDARDS.md) for the full convention (error-handling-by-layer, comment style, naming) - read it before touching client or route code.

### Error handling by layer (see CODING-STANDARDS.md for the full table)

Client layer (`common/clients/**`) returns errors as data (`{"status": "unhealthy", ...}`), never raises from `health_check()`. Service layer raises exceptions. Route layer (`api/**/routes_*.py`) catches them and returns a consistent `{"error": "...", "code": "..."}` shape via `api/dependencies.py`'s `json_error()` - `code` is a stable value from `common/error_codes.py`, always picked explicitly, never defaulted.

## Docs worth reading before non-trivial changes

- [docs/HANDOFF.md](docs/HANDOFF.md) - **read this one first** if picking up the project with no prior context; it's the orientation layer everything else points into (also has the real current branch names - `master`/`develop`/`feature-langchain-rag-pipeline` - after a GitHub rename that left stale `main`/`developer` references elsewhere in git history).
- [docs/RAG-ROADMAP.md](docs/RAG-ROADMAP.md) - phase-by-phase history and current status; historical, not updated retroactively.
- [docs/CODING-STANDARDS.md](docs/CODING-STANDARDS.md) - error handling, logging, comment style, naming, API contract conventions.
- [docs/FAQ.md](docs/FAQ.md) - design-decision rationale (document update strategy, where RAG metadata lives, indexing/categorization).
- [docs/BACKLOG.md](docs/BACKLOG.md) - known gaps, deliberately deferred work.
- [docs/CICD-BRANCHING-STRATEGY.md](docs/CICD-BRANCHING-STRATEGY.md) - branch roles (`feature-*` -> `develop` -> `master`), every CI gate and its threshold.
- [docs/AWS-DEVOPS-RUNBOOK.md](docs/AWS-DEVOPS-RUNBOOK.md) - container -> ECR -> App Runner pipeline, required build flags and why.
- [docs/TESTING-GUIDE.md](docs/TESTING-GUIDE.md) - what's covered, why those cases, the fake-based pattern to copy.
- [docs/S3-ASYNC-UPLOAD-DESIGN.md](docs/S3-ASYNC-UPLOAD-DESIGN.md) - design only, not implemented: today's upload/index is synchronous, local-disk, in-request - don't assume S3/Lambda/async exists anywhere in the actual code.
- [docs/SDD-SPEC-SHEET.md](docs/SDD-SPEC-SHEET.md) - the SDD lifecycle, file map, and a worked example (Phase 16), written as a standalone reference for learning the process, not just following it.
- [postman/hrb_chatbot.postman_collection.json](postman/hrb_chatbot.postman_collection.json) - every endpoint's happy path + edge cases, kept in sync with actual behavior; update it alongside any request/response contract change.

## Spec-Driven Development (SDD)

Adopted 2026-09-14, adapted from a reference pattern (Joshua McDonald's
"Spec-Driven Development with Claude Code") written for an unrelated project.
The core idea, unchanged: **skills are guidance the model can ignore on a
given turn; hooks run on a deterministic path outside the model's control.**
Neither alone is enough - a skill can be skipped under time pressure, a hook
can't be talked out of running.

**No separate `specs/`/`adr/` folder exists here, on purpose.** This project
already had the equivalent: [docs/RAG-ROADMAP.md](docs/RAG-ROADMAP.md) is
both the plan and the history (phase-by-phase, with a "Status at a glance"
table), and [docs/FAQ.md](docs/FAQ.md) already carries decision rationale the
way an ADR would. Adding parallel spec/ADR folders would just create a second
source of truth for the same information - the opposite of what this
codebase's own conventions (single source of truth for defaults, one gateway
per backend type, etc.) are built around. So: **a spec is a `Spec:` sub-list
written into a phase's own bullet** in `docs/RAG-ROADMAP.md`'s `## Phases`
section, before that phase's code starts - see
`.claude/skills/spec-new/SKILL.md` for the exact template. The 14 phases
shipped before this convention existed are marked `Retrofitted (pre-SDD)` in
the "Status at a glance" table's `Spec` column rather than reconstructed after
the fact - their detailed write-ups in `## Phases` already serve as the
historical record.

**Two working norms that apply everywhere, not just to SDD:**
- **One task at a time.** No multi-file autonomous changes across unrelated
  concerns. Finish one phase/task, report, wait for review.
- **Flag, don't fix.** Something noticed outside the current task's scope
  gets a one-line note in the delivery note (see below), not an unprompted
  fix.

**Available skills** (`.claude/skills/<name>/SKILL.md`, each also a
`/<name>` slash command):
`session-start` (loads branch/open work), `delivery-note` (concise end-of-
task summary), `spec-new` (write a phase's spec), `spec-review` (audit a spec
before implementation), `spec-verify` (map tests back to a spec's acceptance
criteria after), `spec-implement` (execute one spec'd phase),
`coding-standards` (thin wrapper over `docs/CODING-STANDARDS.md`),
`architecture-review` (check a design against settled decisions in this file
and `docs/FAQ.md`).

**Subagents:** `.claude/agents/implementer.md` - executes one already-spec'd
phase in an isolated context. `.claude/agents/code-reviewer.md` - read-only,
flags `docs/CODING-STANDARDS.md`/scope/security issues on a phase's diff
before its roadmap checkbox flips to done; never edits or fixes ("flag,
don't fix" applies to it most of all). No `integrator` subagent (that
exists in the reference pattern for a multi-engineer team running parallel
mini-specs in separate worktrees - this is a solo developer plus one
Claude Code session, so there's nothing to integrate). No `spec-decompose`
skill for the same reason.

**No Core-AI-Engineering-is-owner-only restriction.** Some SDD setups (the
reference pattern's own source project included) restrict the agent from
touching retrieval/chunking/prompt-assembly code, reserving it for a human
owner. That doesn't apply here - Claude Code has built this project's full
RAG pipeline directly, phase by phase, with the user's explicit request and
review each time (see `docs/RAG-ROADMAP.md`'s Phase 4/14 entries). The
`implementer` subagent may work in any layer; its boundary is the phase's
spec, not an architectural layer.

**Hooks** (`.claude/settings.json`): `SessionStart` runs the session-start
check automatically; `PreToolUse` (`.claude/scripts/spec_gate.py`) blocks a
`Write`/`Edit` under `src/hrb_chatbot/**` unless `docs/RAG-ROADMAP.md` has at
least one `- [ ]` phase with a written `**Spec:**` block - added 2026-09-14
after Phase 16 (the content-hash duplicate-upload fix) proved the spec-first
convention out on a real change; `PostToolUse` runs the test suite in the
background after a `src/`/`tests/` edit and surfaces only failures; `Stop`
asks a small model whether the turn's own final message describes something
left untested/incomplete before letting the turn end, and denies (asks for
more work) only on a clear-cut case.

**What the `PreToolUse` gate does and doesn't check:** it confirms *a* spec
is open, not that the specific edit falls inside that spec's declared scope
- it can't verify that automatically. Staying in scope is `implementer.md`'s
job (a stated hard rule), not this hook's. It's also scoped to
`src/hrb_chatbot/**` only, deliberately - never `.claude/`, `tests/`, or
`docs/` - so a bug in the gate itself, or in any skill/hook file, can never
lock out fixing it (this is why the `Stop` hook's own prompt bug, found and
fixed live on 2026-09-14, was fixable at all: `.claude/settings.json` isn't
gated).
