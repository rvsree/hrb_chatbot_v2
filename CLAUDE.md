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

`main.py` (FastAPI app + global exception handlers) -> `api/**/routes_*.py` (routers, one per resource, Pydantic request/response models only - see `models/`) -> `services/*.py` (thin orchestration layer, exists so routers never import `ai/` directly) -> `ai/**/pipeline.py` (the actual RAG logic) -> `common/clients/**` (one class per external backend, behind a gateway).

There are **two separate pipelines** under `ai/`, easy to confuse by name:
- `ai/doc_processing/pipeline.py` - **ingestion**: extract PDF text -> chunk -> embed -> index. Driven by `POST /v1/rag-ingestion/documents/{id}/index`.
- `ai/rag_pipeline/pipeline.py` - **query**: decompose -> retrieve -> generate. Driven by `POST /v1/rag-retrieval/query`.

`ai/agents/`, `ai/pre_processing/` (guardrails, query decomposition, search filtering), `ai/rag_pipeline/helper/access_control.py`, `ai/rag_pipeline/tools/`, and `common/observability/` are empty placeholder files (0 bytes) - scaffolding for future phases per the roadmap, not dead code to clean up.

### Three different libraries, one per pipeline stage, deliberately

This mirrors the workshop's own module structure - not an accident, don't "consolidate" onto one library:
- **Chunking** (`ai/doc_processing/chunking/text_chunker.py`) - LangChain's own splitters, 6 selectable strategies via a `CHUNKING_STRATEGIES` dict (name -> function), auto-selected by `decide_chunking_strategy()` when not given explicitly.
- **Indexing** (`ai/doc_processing/indexing/vector_indexer.py`) - LlamaIndex's `VectorStoreIndex` for the actual vector write; everything around it (stale-id diffing, delete, `is_current` flips on supersede) is this project's own logic, not LlamaIndex's.
- **Search/retrieval** (`ai/rag_pipeline/query_retrieval/retriever.py`) - raw LangChain (`langchain_chroma`/`langchain_pinecone`), two plain functions (similarity, MMR) via a `SEARCH_STRATEGIES` dict, no classes - matches the workshop demo's own style.

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
- [postman/hrb_chatbot.postman_collection.json](postman/hrb_chatbot.postman_collection.json) - every endpoint's happy path + edge cases, kept in sync with actual behavior; update it alongside any request/response contract change.
