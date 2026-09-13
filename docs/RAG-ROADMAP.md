# RAG boilerplate roadmap — division of labor

Durable copy of the plan agreed on 2026-09-07, so it survives independently
of any one chat session. Update the phase statuses below as they land; don't
delete a row when it's done.

## Why this split exists

This project is being built by hand, deliberately, to apply what's being
learned in the Interview Kickstart FDE cohort's RAG modules (the instructor's
own workshop, `support_desk_rag_workshop/SupportDesk-RAG-Workshop`, was
reviewed to inform this roadmap: embeddings → chunking → indexing strategies
→ RAG pipeline with anti-hallucination → two-layer evaluation → agentic RAG).

So the split is intentional: Claude Code builds the boilerplate - FastAPI
endpoints, request/response models, and the client files that read `.env` and
connect to backend services. Every piece of actual RAG logic - chunking,
embedding orchestration, indexing, retrieval, grounded response generation,
evaluation - is implemented by hand, using the workshop's concepts.

A second reference project, `hrb_emp_assist`, was reviewed and deliberately
**not** reused above the vector-DB-client layer - its service/repo/router/model
layers for this same feature run ~2,550 lines for what should be small,
a direct result of repeated refactoring visible in its own `docs/` folder.
Only its small, clean `chroma_db_client.py` (127 lines) informed (not was
copied into) the client below.

## The seam

| Layer | Who | Location |
|---|---|---|
| FastAPI routes, request/response models | Claude Code | `api/rag/`, `models/` |
| Raw file storage, document metadata | Claude Code | `services/documents_service.py` |
| Vector DB client (ChromaDB active, Pinecone real+tested alternative) + gateway | Claude Code | `common/clients/db_client/` |
| Document-metadata client (SQLite active, Postgres real+tested alternative) + gateway | Claude Code | `common/clients/db_client/` |
| Health check wiring | Claude Code | `api/admin/health_checks.py` |
| Chunking strategy | Claude Code *(planned hand-written; built on explicit request - see Phase 4)* | `ai/doc_processing/chunking/` |
| Embedding orchestration | Claude Code *(same override)* | `ai/doc_processing/embedding/` |
| Indexing, insert/update logic | Claude Code *(same override)* | `ai/doc_processing/indexing/` |
| Retrieval + grounded generation | **Hand-written** | `ai/rag_pipeline/query_retrieval/`, `ai/rag_pipeline/response_generation/` |
| Evaluation | **Hand-written** | `ai/rag_pipeline/evaluations/` |
| Agentic RAG (later, optional) | **Hand-written** | `ai/agents/` |

Claude Code's boilerplate calls into the hand-written code through plain
Python entry points (`index_document(...)`, `answer_query(...)`) that raise
`NotImplementedError` naming the module to fill in, until it exists - the
same pattern already used for `PineconeClient`'s stub and for `check_tools()`
in `health_checks.py`.

## Status at a glance

Updated 2026-09-08. This table is the fast-read summary; the full "Phases"
section below it is the authoritative detail - if the two ever disagree,
the detail below is correct and this table is stale, not the other way
around.

| Phase | Who | Status |
|---|---|---|
| 1 — ChromaDB client + gateway | Claude Code | ✅ Done |
| 2 — Document upload API | Claude Code | ✅ Done |
| 2.5 — Postgres metadata store | Claude Code | ✅ Done |
| 2.6 — Pinecone vector store | Claude Code | ✅ Done |
| 3 — Indexing trigger endpoint | Claude Code | ✅ Done |
| 4 — Chunking/embedding/indexing | Claude Code (override) | ✅ Done |
| 4.1 — Per-call config overrides | Claude Code (override) | ✅ Done |
| 4.2 — Document metadata expansion + content-hash dedup | Claude Code (override) | ✅ Done, 2026-09-10 |
| 4.3 — Delete endpoint | Claude Code (override) | ✅ Done, 2026-09-10 |
| 4.4 — Document versioning (supersede + is_current retrieval filtering), table extraction, document-metadata extraction | Claude Code (override) | ✅ Done, 2026-09-11 |
| 4.5 — Retrieval relevance threshold, standardized error codes | Claude Code | ✅ Done, 2026-09-11 |
| 5 — Query endpoint, stubbed | Claude Code | ✅ Done |
| 5.1 — Query decomposition | Hand-written | 📋 Planned |
| 5.2 — Query variants | Hand-written | 📋 Planned |
| 5.3 — Prompt chaining + versioning | Hand-written | 📋 Planned |
| 6 — Retrieval + grounded generation | Claude Code (override, 2026-09-10) | 🚧 MVP done - real retrieval + generation, no COT/guardrails yet; see Phase 6 detail below |
| 6.1 — Contracts/validation for query path | Claude Code | ✅ Done alongside the Phase 6 MVP - `model_used` added to `RagQueryResponse` |
| 7 — Guardrails (input + output) | Hand-written | 📋 Planned |
| 8 — Golden dataset + evaluations + A/B | Hand-written | 🚧 Golden dataset done (override, 2026-09-08); evaluations/A/B harness still 📋 planned |
| 9 — Bedrock as an LLM provider | Claude Code | ✅ Done |
| 10 — Docker + AWS deployment (App Runner) | Claude Code | ✅ Done - `RUNNING`, verified live (shallow + deep health, real Pinecone query); Postgres/Neon leg still pending the user's Neon signup (documented compromise, not a blocker) |
| 11 — CI/CD + GitHub | Claude Code | ✅ CI verified passing on GitHub Actions (pytest included as of Phase 12); deploy workflow written but unexercised - needs `main` merge + 2 GitHub Secrets still pending from the user |
| 12 — REST API contract-first hardening | Claude Code | ✅ Done - versioning, idempotency, rate limiting, validation bounds, error handling, pre-flight checks, all verified live and unit-tested |
| 13 — Branch restructuring + CI/CD gates | Claude Code | ✅ Done - `main`/`developer`/`feature-kb-indexing-rag-pipeline` renamed to `master`/`develop`/`feature-langchain-rag-pipeline` on GitHub; `deploy.yml`/`ci.yml` triggers fixed to match; coverage floor, `bandit`, `pip-audit`, and a real post-deploy smoke test added to CI/CD; see `docs/CICD-BRANCHING-STRATEGY.md` |
| 14 — LangChain/LlamaIndex pipeline rewrite (chunking, indexing, search), idempotency removed | Claude Code | 🚧 In progress, on `feature-langchain-rag-pipeline`. 14.1 (idempotency removal) done, 14.2 chunking + indexing sub-phases done; search/retrieval sub-phase not yet started |

**If you're picking this up after a restart with no session memory**, the
one thing to check first is Phase 10's actual live AWS state - it does not
show up by reading code, only by querying AWS directly:
```
aws apprunner describe-service --region us-east-1 \
  --service-arn arn:aws:apprunner:us-east-1:418884736369:service/hrb-chatbot/f957548202f343aa8ca91f341d71d85a
```
(needs `aws-cli` ≥ 2.something-with-apprunner, or run the equivalent
`boto3` call - see Phase 10 below for why the CLI here may still be too old).
Note the ARN above is the **final, working** service - two earlier attempts
(`63fcfce613a5425ab43cf8fd8dad8228`, `09f425485ee646379d68acc950570bcd`)
were deleted after `CREATE_FAILED` and are dead references if you find them
anywhere else in this file's own history below - see Phase 10's "Three real
bugs found the hard way" for why.

## Phases

- [x] **Phase 1 (Claude Code) — ChromaDB client + gateway.**
  `common/clients/db_client/chroma_client.py`, `db_gateway.py`.
  `health_checks.py`'s `check_vector_database()` wired into `check_all_backend_services()`.
  Verified: `GET /health?deep=true` reports ChromaDB healthy (persistent
  mode, `data/chroma_db/chroma.sqlite3` created).
- [x] **Phase 2 (Claude Code) — Document upload API.** `POST /rag/documents`
  (single/batch, one result per file - partial success, not all-or-nothing),
  `GET /rag/documents`, `GET /rag/documents/{id}`. Raw file storage in
  `data/uploads/{document_id}/`. Metadata behind the same abstract-client
  pattern as the vector store: `base_metadata_client.py` (the contract),
  `sqlite_client.py` (real), `postgres_client.py` (stub, same reasoning as
  `PineconeClient` - not something the original plan called out explicitly,
  added because the same swap-later need applies here). PDF-only and
  20MB-max validation in `services/documents_service.py`.
  Verified live: single upload, a real PDF from `resources/kb_docs/`; batch
  upload with one valid PDF + one deliberately invalid `.txt` file, confirmed
  the good one is stored and the bad one is rejected with a clear reason in
  the same response, not a blocked batch; list, get-by-id, and 404-on-unknown-id
  all confirmed. `GET /health?deep=true` now also reports `metadata_database`
  (SQLite) alongside `vector_database` (renamed from `database` for clarity
  now that there are two kinds).
- [x] **Phase 3 (Claude Code) — Indexing trigger, stubbed.** `POST
  /rag/documents/{id}/index` in `api/rag/routes_documents.py`, calling
  `ai/doc_processing/pipeline.py::index_document()` - a scaffold, not an
  implementation: `chunk_document()` / `embed_chunks()` / `index_chunks()`
  each raise `NotImplementedError` naming the folder and workshop module to
  use, with the already-working calls to reach for
  (`get_client_gateway().openai_embedding()`, `get_db_gateway().chroma()`)
  spelled out in the docstrings. Verified live: a real uploaded document
  returns `501` with the exact message above, an unknown id returns `404`,
  and the document's status correctly stays `uploaded` rather than being
  falsely marked `indexed` when the pipeline isn't implemented.
- [x] **Phase 4 (Claude Code, built on explicit request 2026-09-08 —
  overrides the original "hand-written" plan).** The user asked for this
  phase by name, after being told directly it was the pipeline they'd
  earlier said they wanted to write themselves - a deliberate, informed
  choice to have it built now, not drift. Recorded here so it's clear this
  one didn't follow the original division of labor, and why.

  - **`ai/doc_processing/chunking/text_chunker.py`** - a recursive
    character splitter written natively (no `langchain-text-splitters`):
    tries paragraph breaks first, falls back to sentences then plain
    characters for a piece still too big, then merges small pieces back up
    to `chunk_size` (1000 chars) with `chunk_overlap` (150 chars) carried
    forward. Workshop Module 2's strategy.
  - **`ai/doc_processing/embedding/embedding_generator.py`** - calls the
    already-built `client_gateway().openai_embedding().get_embeddings()`.
    Workshop Module 1.
  - **`ai/doc_processing/indexing/vector_indexer.py`** - the insert/update
    logic. Chunk ids are deterministic
    (`f"{document_id}:{chunk_index}"`), so a re-index naturally overwrites
    chunks that still exist - but a document that *shrinks* would leave
    its excess old chunks orphaned in the vector store if that were all
    this did. So a `chunk_ids` column was added to the metadata store
    (SQLite/Postgres - see `base_metadata_client.py`'s `set_chunk_ids()`)
    recording exactly which ids a document's *previous* index produced;
    a re-index diffs against that list and deletes whatever isn't part of
    the new set before recording the new one. Writes through
    `db_gateway().vector_store()` - never a hardcoded backend - so this
    logic is identical regardless of `RAG_VECTOR_DB`.
  - **`RAG_VECTOR_DB=chromadb|pinecone`** (new `.env` switch) - read once,
    in `db_gateway.vector_store()`.

  Verified live, real cost incurred (a few cents, embedding actual PDF
  text): `POST /rag/documents/{id}/index` on `JPMC Healthcare Benefits.pdf`
  → 39 real chunks, `action: "insert"`. Re-running the identical call →
  `action: "update"`, `chunks_removed: 0` (nothing stale, same content).
  Then the case that actually proves the update logic, not just its
  reporting: called `index_chunks()` directly with 3 fake chunks for the
  *same* document (simulating a shrink) → `chunks_removed: 36`, and the
  ChromaDB collection's real vector count dropped to exactly 3, not 42 -
  confirming the old chunks were actually deleted, not left behind
  alongside the new ones. Restored the document to its real 39-chunk
  content afterward. Switched `RAG_VECTOR_DB` to `pinecone`, indexed a
  second document (`JPMC Paid TimeOff.pdf`) → 45 chunks landed in
  Pinecone's `hrb_chatbot_kb` namespace while ChromaDB's count stayed at
  39, untouched - confirming the switch actually isolates the two
  backends rather than one silently winning. Re-indexed that same
  document on Pinecone → `action: "update"` there too. `RAG_VECTOR_DB`
  restored to `chromadb` afterward (the established default).

- [x] **Phase 4.1 (Claude Code, on request 2026-09-08) — per-call config
  overrides.** `POST /rag/documents/{id}/index` now takes an optional JSON
  body (`models/documents.py`'s `IndexRequest`) - `vector_db`, `chunk_size`,
  `chunk_overlap`, `embedding_model` - each defaulting to the .env-wide
  setting when omitted. `db_gateway.vector_store()` now takes a `provider`
  override and **raises on an unrecognized name** instead of silently
  falling back to ChromaDB (a gap the user's own audit questions surfaced -
  see the "Known gaps" note below). The response (`IndexResponse`) reports
  which resolved values actually ran, not just the outcome - useful for
  confirming an override took effect without re-reading `.env`.

  **Known limitation, documented in `vector_indexer.py`, not solved:** if
  the same document is indexed to store A, then later indexed again with
  `vector_db` overridden to store B, the metadata store's `chunk_ids`
  afterward only describes store B - store A's chunks are neither migrated
  nor cleaned up, and a subsequent default-store re-index will report
  `chunks_removed` against ids that live in the *other* store (a harmless
  no-op there, but the count is misleading). Reproduced live while testing
  this feature, not hypothetical - cleaned up by hand afterward. Safe as
  long as one document is always indexed to the same store; switching
  per-document is out of scope for what this override was built for.

  Verified: indexing with no body → defaults reported back exactly
  (`chromadb`, `text-embedding-3-small`, 1000/150); indexing with
  `{"vector_db": "pinecone", "chunk_size": 500, "chunk_overlap": 50}` →
  76 chunks (smaller chunk size, more chunks, as expected), landed in
  Pinecone for that call; `{"chunk_size": 500, "chunk_overlap": 600}`
  (overlap ≥ size) → `422` with a clear validation message, not a
  confusing failure downstream.

- [x] **Phase 4.2 (Claude Code, on request 2026-09-10) — document metadata
  expansion + content-hash dedup.** Two related changes to the `documents`
  table (SQLite + Postgres, migrated the same lazy `ADD COLUMN` way
  `chunk_ids` was):

  - **New columns**: `document_version` (1 on upload, +1 on every
    successful index), `chunk_count`, `embedding_model`,
    `embedding_dimension` (measured from the real embedding vector's
    length, not a hardcoded model→dimension table), `vector_db`,
    `chunk_size`, `chunk_overlap`, `last_indexed_at` (distinct from
    `updated_at`, which also moves on a failed attempt), `file_size_bytes`.
    All written in one new `record_successful_index()` call, replacing the
    old separate `set_chunk_ids()` + `update_status("indexed")` pair.
  - **Content-hash dedup**: every upload is SHA-256'd; a match against an
    existing document's `content_hash` (new column + index) returns that
    existing document instead of creating a new one (`status: "duplicate"`
    in the response, plus a new `duplicate_count` on
    `DocumentUploadResponse`). Persistent and header-independent - unlike
    the `Idempotency-Key` cache, it catches identical content uploaded at
    any time, survives restarts, since it's backed by the real DB.

  Verified live: re-uploading the identical file twice → second call
  returns `status: "duplicate"` pointing at the first upload's
  `document_id`, no new row created. Verified the full insert→update cycle
  separately: upload → `document_version: 1`; first `/index` →
  `action: "insert"`, version → 2; second `/index` on the same id →
  `action: "update"`, version → 3. 11 tests (8 upload/dedup, uuid-salted
  content per test since these hit the real persistent SQLite file with no
  per-test reset - a fixed literal would collide across separate test
  *runs*, not just within one).

- [x] **Phase 4.3 (Claude Code, on request 2026-09-10) — delete endpoint.**
  `DELETE /v1/rag-ingestion/documents/{id}` (`documents_service.delete_document()`) -
  a full delete, not selective: a document has one current state (no
  retained version history to pick a version from - see Phase 4.2's
  `document_version`, which is a counter, not stored history). Removes, in
  order: the vector store's chunks (using the metadata store's `chunk_ids` -
  skipped if the document was never indexed), the metadata row, and the
  uploaded file on disk.

  **Ordering is deliberate, same safety reasoning as the insert/update
  path**: vectors are deleted first, while `chunk_ids` still exists to find
  them; the metadata row (the only record of which vector ids belong to
  this document) is removed last, once vectors are confirmed gone. A crash
  mid-way leaves the metadata row intact so a retry can still finish the
  job, rather than orphaning vectors with no way left to find them.

  Verified live against real data, not just SQLite: indexed a real document
  (40 real chunks) → confirmed via a direct Chroma query
  (`collection.count()`, `collection.get(where={"document_id": ...})`) that
  the vector store held 85 total / 40 for this document → called `DELETE`
  → vector store count dropped to 45 (exactly the 40 removed), `GET` on the
  id now `404`, and `data/uploads/{id}/` gone from disk. 4 new tests
  (delete-then-gone, unknown id `404`, double-delete `404` the second
  time) - vector-store deletion itself is verified live rather than
  in the automated suite, matching this project's existing practice of not
  spending real embedding/API cost inside `pytest`.

- [x] **Phase 4.4 (Claude Code, on request 2026-09-11) — document versioning,
  table extraction, document-metadata extraction.** Three related additions,
  built and tested primarily against ChromaDB (free, local) - Pinecone
  portability confirmed by design (both clients share `BaseVectorDBClient`;
  `update_metadata()` was added to both), not yet exercised live against a
  real Pinecone index; that's the deliberately deferred next step, once this
  round is stable.

  **Normalized `chunks` table** (SQLite + Postgres) - one row per chunk
  (`chunk_id`, `document_id`, `chunk_index`, `created_at`, `is_current`),
  replacing the need to parse `documents.chunk_ids`' JSON blob for any
  per-chunk query. Populated inside `record_successful_index()` (delete-then-
  insert per document, same shape as the vector store's own stale-chunk
  cleanup).

  **Document versioning via explicit supersede** - `POST
  /v1/rag-ingestion/documents` gained an optional `supersedes_document_id`
  form field (rejected with 422 on a batch upload - ambiguous which file
  would supersede it; rejected as a per-file "rejected" result if the target
  id doesn't exist). Upload only *records* the intent
  (`documents.supersedes`); the old document isn't flipped until the *new*
  one successfully indexes (`metadata_store.mark_superseded()`, called from
  `vector_indexer.py`, only on that document's first index - not repeated on
  a later re-index) - so there is never a window where neither version's
  content is live. The flip touches three places: the old document's own SQL
  row (`is_current=false`, `superseded_by` set), its rows in `chunks`, and -
  via the vector store's new `update_metadata()` (added to
  `BaseVectorDBClient`, implemented in both Chroma and Pinecone) - its actual
  vectors' metadata, without a wasted re-embed.

  **Retrieval excludes superseded chunks by default** -
  `retriever.py`'s vector-store query now always filters
  `where={"is_current": {"$ne": False}}` - `$ne`, not an `is_current: true`
  equality match, deliberately: chunks indexed before this field existed
  have no `is_current` key at all, and an equality filter would have
  silently excluded those too. Only a chunk explicitly flipped to `false`
  is excluded; nothing is deleted, so superseded content stays available for
  direct/audit lookup (`collection.get(ids=...)`), just not surfaced to a
  normal query.

  **Table-aware PDF extraction** - new `ai/doc_processing/tables/table_extractor.py`
  (pdfplumber, a new dependency - pypdf's `extract_text()` has no table
  awareness at all). Tables are extracted separately per page, formatted as
  markdown, and appended after the main extracted text (not inlined at their
  original position - reconstructing exact layout position isn't needed for
  chunking, only keeping row/column structure readable is).

  **LLM-based document-metadata extraction** - new
  `ai/doc_processing/metadata_extraction/document_metadata_extractor.py`.
  Sends the first ~3000 characters of extracted text to the chat LLM, asking
  for owner/department/doc_type/purpose as JSON (explicitly told to answer
  `null`, not guess, for anything the text doesn't support). Runs once, on a
  document's first successful index only (the result can't change between
  re-indexes of the same content, so it's never re-billed on a re-index).
  Best-effort by design: any extraction or parsing failure is logged and
  swallowed, never allowed to fail the index itself.

  **Verified live, real cost incurred** (not just unit-tested): uploaded a
  real PDF with a real table (years-of-service → disability-pay-percentage),
  indexed it, and confirmed via a direct Chroma query that a chunk contained
  the table correctly reformatted as markdown. Confirmed document-metadata
  extraction produced an accurate `doc_type` and one-sentence `purpose`
  summary, and correctly returned `null` (not a hallucinated guess) for
  `owner`/`department`, which the source document doesn't state. Ran the
  full supersede flow end to end: uploaded v1, indexed it; uploaded v2 with
  `supersedes_document_id` pointing at v1, indexed v2; confirmed v1 flipped
  to `is_current: false` with `superseded_by` set, confirmed v1's vectors
  are still physically present in Chroma (`collection.get(ids=...)` still
  returns them) but `is_current: false`; then ran a real
  `POST /v1/rag-retrieval/query` and confirmed **all 5** returned sources
  were v2's chunks, **zero** from v1 - the actual point of the whole feature,
  proven against a real query, not inferred from the write path alone.

  17 new tests (fakes only, zero network): `vector_indexer.py`'s
  `is_current`/timestamp tagging and full supersede-propagation flow
  (including that a *second* re-index doesn't repeat the flip);
  `retriever.py`'s exclusion of superseded chunks and backward-compatible
  handling of chunks with no `is_current` field at all;
  `document_metadata_extractor.py`'s clean/messy/failed LLM-response
  handling; `table_extractor.py`'s markdown formatting; and route-level
  validation for `supersedes_document_id` (batch rejection, unknown-target
  rejection, successful recording). 76/76 total suite passing, stable across
  repeated runs.

- [x] **Phase 4.5 (Claude Code) — retrieval relevance threshold, standardized
  error codes.** Two fixes found by reviewing a real query response, not
  planned in advance.

  **Relevance threshold**: `retriever.py` previously returned exactly
  `top_k` results regardless of whether any were actually relevant - a
  question about content nothing indexed covers still got "sources" that
  looked plausible next to a correctly-hedged answer. Root cause in the one
  case that surfaced this was pure data (a document uploaded but never
  indexed), not a bug - but the underlying gap (no relevance floor) is
  real regardless. Added `_meets_relevance_bar()`, direction-aware per
  backend (Chroma's distance is lower=better, Pinecone's score is
  higher=better). `MAX_CHROMA_DISTANCE = 1.1` is empirically calibrated,
  not guessed: a real query's genuinely relevant chunks scored ~0.69-0.97,
  its irrelevant ones (once nothing relevant was indexed) scored
  ~1.22-1.27 - 1.1 sits between the two clusters with margin either side.
  `MIN_PINECONE_SCORE = 0.5` is a reasoned starting point only, not yet
  calibrated against a real Pinecone query. When every retrieved chunk
  fails the bar, `chunks` comes back empty, which already triggers
  `generate_answer()`'s existing no-context short-circuit - so this also
  means a genuinely unanswerable question no longer spends an LLM call at
  all. Verified live: re-ran the exact query that surfaced this after
  indexing the real content it needed (10/10 correctly-sourced chunks),
  then a genuinely unanswerable question (`sources: []`, no LLM call).

  **Standardized error codes**: every error response now carries a stable
  `code` (new `common/error_codes.py`) alongside its human-readable
  `error` message - `json_error()`'s `code` parameter is required, not
  optional, so a call site can't silently omit one. Found two real shape
  inconsistencies while doing this, not just adding a field on top of what
  existed: `RequestValidationError` (422) and `rate_limiter.py`'s raw
  `HTTPException(429)` both bypassed `json_error()` entirely, returning
  FastAPI's own `{"detail": ...}` shape - contradicting what
  `docs/HANDOFF.md`/`README_TEST.md` already claimed ("every error has the
  same shape"). Two new global handlers in `main.py` fix both, and
  `json_error()` gained a `headers` parameter (separate from the JSON body
  extras) so the 429 handler can preserve the real `Retry-After` header
  rather than accidentally serializing it into the response body.
  `DocumentUploadResult` also gained `error_code` for per-file upload
  rejections (`INVALID_FILE_TYPE`, `EMPTY_FILE`, `FILE_TOO_LARGE`, etc.) -
  the same "give a caller something to branch on, not just prose"
  reasoning applies to a batch-uploading caller deciding which files are
  worth retrying. Motivated directly by the planned agent work: a
  LangGraph tool-calling loop needs a stable decision surface, not string-
  matching message text. 9 new/extended tests, including two direct unit
  tests of the new exception handlers (not routed through 100 real
  requests to trip rate limiting) and live verification that the 422 shape
  actually changed. 81/81 total suite passing.

## Phase 5 onward — RAG query, evaluations, guardrails, deployment

Added 2026-09-09, tracking a much larger discussion in one place rather
than losing it across chat history. Confirmed with the user: the original
division of labor (Claude Code = boilerplate/contracts, hand-written = RAG
logic) **still holds** for everything below - chunking/embedding/indexing
(Phase 4) was a one-time, explicitly-requested exception, not a precedent.
Every phase below says who builds it for that reason. ChromaDB only for
all of this, per explicit instruction - Pinecone stays available (Phase
2.6) but isn't exercised again until this core is standardized. Explicitly
**deferred, not forgotten**: ReAct multi-agents, MCP tools, caching - a
later, separate wave once this core is solid.

- [x] **Phase 5 (Claude Code) — Query endpoint, stubbed.** `POST /rag/query`
  (`api/rag/routes_query.py`) - real request/response contract
  (`RagQueryRequest`/`RagQueryResponse` in `models/rag.py`, including
  `RetrievedChunk` for sources), logging, error handling - calling
  `services/rag_service.py` → `ai/rag_pipeline/pipeline.py::answer_query()`,
  a three-function scaffold (`decompose_query`/`retrieve_chunks`/
  `generate_answer`, mirroring `ai/doc_processing/pipeline.py`'s pattern
  exactly) that raises `NotImplementedError` naming the exact file and
  workshop module for each step.

  Verified live at the time: a valid query → `501` naming
  `ai/pre_processing/query_decompose.py` and Phase 5.1 specifically (not a
  generic error); empty `query` → `422` (min length); `top_k=100` → `422`
  (max 20) - both caught by the contract before a handler ever runs, not
  downstream. Confirmed no regression on `/health`, `/docs`, or the
  existing `/rag/documents` endpoints. **Superseded by Phase 6 below** -
  the `501` is no longer what a valid query returns; the `422` validation
  behavior is unchanged.
- [ ] **Phase 5.1 (hand-written) — Query decomposition.** `ai/pre_processing/
  query_decompose.py`. **LLM-based, not classical NLP** - confirmed with
  the user: a single prompt asking the model to break a complex question
  into 2-4 simpler sub-questions (the pattern LlamaIndex's own
  `SubQuestionQueryEngine` uses), not POS-tagging/dependency-parsing. No
  new dependency needed - the existing OpenAI client covers this.
- [ ] **Phase 5.2 (hand-written) — Query variants (multi-query expansion).**
  Generating alternate phrasings of one query to widen retrieval recall
  before merging results. `ai/pre_processing/` or a new module alongside
  query decomposition - exact home to be decided when this is picked up.
- [ ] **Phase 5.3 (hand-written) — Prompt chaining + prompt versioning.**
  `ai/rag_pipeline/prompts/` (currently empty). A registry/versioning
  scheme for prompts used across decomposition, generation, and
  evaluation - not just a hardcoded string per call site.
- [x] **Phase 6 (Claude Code, built on explicit request 2026-09-10 - overrides
  the original "hand-written" plan, same pattern as Phase 4) — MVP
  retrieval + grounded generation.** The user asked directly for this
  ("impl logic for rag search... endpoint"), after Phase 4's chunking/
  embedding/indexing had already set the precedent that this project's
  division of labor bends when explicitly, knowingly overridden - not a
  silent drift. Recorded here for the same reason Phase 4 was: so it's
  clear this didn't follow the original hand-written boundary, and why.

  - **`ai/rag_pipeline/query_retrieval/retriever.py`** - embeds the query
    (`OpenAIEmbeddingClient`), searches the configured vector store,
    deduplicates chunks by `(document_id, chunk_index)` (so a chunk found
    by more than one sub-query is only returned once - already written to
    support Phase 5.1's future multi-query output without its own
    signature changing), and attaches each chunk's source `filename` from
    the metadata store - one lookup per distinct document, not per chunk.
  - **`ai/rag_pipeline/response_generation/generator.py`** - builds a
    grounded prompt (context blocks labeled `[filename, chunk N]`, an
    explicit "answer using ONLY the context... say you don't know
    otherwise" instruction folded into the question text, since
    `BaseLLMClient.ask()` has no separate system-message parameter).
    Empty retrieval short-circuits to a fixed "no information" answer
    without spending an LLM call. `model_name` override builds a fresh,
    one-off `OpenAIChatClient` (mirroring how `IndexRequest.embedding_model`
    overrides `get_embeddings()`, since `ask()` has no per-call model
    parameter to piggyback on); no override uses the shared `ClientGateway`
    instance.
  - **`ai/rag_pipeline/pipeline.py`'s `decompose_query()`** stays a
    **trivial passthrough** (`return [query]`) - this is explicitly NOT
    Phase 5.1. Real LLM-based decomposition remains hand-written, untouched,
    in `ai/pre_processing/query_decompose.py` (still empty). The passthrough
    exists only so `retrieve_chunks()` already accepts a list of sub-queries
    without needing a signature change once Phase 5.1 lands for real.
  - **Deliberately not built in this MVP**: chain-of-thought prompting,
    query decomposition, multi-query expansion, prompt versioning (Phase
    5.1-5.3), and both directions of guardrails (Phase 7) - explicitly
    scoped out by the user ("keeping MVP deliverables in mind... I will
    identify and pick up some other tasks later").

  **Response contract also updated** (folded into this phase rather than
  a separate Phase 6.1 pass): `RagQueryResponse` gained `model_used` -
  the actually-resolved chat model, not just the possibly-null override -
  matching the same "report what actually ran" convention `IndexResponse`
  already established. `RetrievedChunk.filename` (added ahead of this
  phase, alongside the document-metadata expansion) is now genuinely
  populated instead of an unused contract field.

  **Verified live, real cost incurred** (one real embedding call + one real
  chat completion): asked "How many weeks of paid time off do employees
  get per year?" against a real indexed document
  (`JPMC Paid TimeOff.pdf`) → a correct, grounded answer ("3 to 5 weeks of
  vacation annually based on years of service and pay grade"), traceable
  to the real retrieved chunk text, with `sources` correctly showing the
  real `filename`. Also unit-tested with fakes (no network): 9 tests
  across `retriever.py` (filename attachment, sub-query dedup, missing-
  metadata fallback, `top_k` limiting) and `generator.py` (no-chunks
  short-circuit, grounding instruction present in the prompt, shared vs.
  overridden client selection). Route-level tests updated to monkeypatch
  `rag_service.answer_query()` rather than asserting the old `501` - one
  of the pre-existing tests was found making a real, uncontrolled OpenAI
  call before this fix.
- [x] **Phase 6.1 (Claude Code) — Contracts/validation/logging for the query
  path.** Folded into Phase 6 above rather than a separate pass -
  `model_used` is the concrete contract addition; the existing
  `json_error()`/try-except/logging shape from upload/indexing already
  covered the rest and needed no changes.
- [ ] **Phase 7 (hand-written) — Guardrails, both directions.**
  `ai/pre_processing/guardrails_input.py` (currently empty) - a validation
  gateway for the incoming query before it reaches retrieval.
  `ai/rag_pipeline/response_generation/guardrails_output/` (currently
  empty) - validates/filters the generated answer before it's returned.
- [ ] **Phase 8 (hand-written, golden dataset sub-item overridden 2026-09-08) —
  Golden dataset + A/B testing + evaluations.**
  `ai/rag_pipeline/evaluations/` (currently empty) - the evaluation metrics
  and A/B harness themselves remain hand-written and unbuilt: Workshop
  Module 5 (retrieval metrics: Precision@K/Recall@K/F1; generation
  metrics: groundedness/completeness via LLM-as-judge).

  **The golden dataset itself is done** - `resources/golden_dataset/golden_dataset.json`,
  22 cases, every fact read directly from the real PDF text in
  `resources/kb_docs/` (not summarized from memory): 18 grounded
  single-document cases across all six documents, 1 cross-document
  synthesis case, and 3 adversarial cases (a question entirely outside
  the knowledge base, a number the source document genuinely doesn't
  state, and a false-premise question the answer should correct rather
  than agree with). Built as an explicit, one-time override of this
  phase's hand-written boundary - same pattern as Phase 4
  (chunking/embedding/indexing), not a precedent for the rest of Phase 8.
  Can now actually be exercised against `POST /v1/rag-retrieval/query`
  since Phase 6's MVP landed - the evaluation metrics/A/B harness
  themselves (Precision@K/Recall@K/F1, groundedness via LLM-as-judge)
  are still the unbuilt, hand-written part of this phase.
- [x] **Phase 9 (Claude Code) — Bedrock as an LLM provider.**
  `BedrockChatClient` implementing `BaseLLMClient` via the Converse API, wired
  into `/health` the same way as OpenAI/Anthropic/OpenRouter
  (`provider=bedrock`) and into `client_gateway.py`'s lazy accessor pattern.
  `ask_with_tools()`'s OpenAI↔Bedrock tool-format conversion is untested
  against a real tool-calling request - only `ask()` and the deep health
  check have been exercised live.

  One thing worth knowing, not glossed over: the deep health check
  (`GET /health?deep=true&provider=bedrock`) passed against a real AWS
  account (122 models visible) using credentials this project never
  configured - `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are both blank in
  `.env`, so boto3's default credential chain fell through to a
  pre-existing `~/.aws/credentials` file already on this machine (confirmed
  via `boto3.Session().get_credentials().method` ==
  `"shared-credentials-file"`), unrelated to this project. Asked the user
  whether to pin project-specific credentials instead; the user chose to
  keep relying on the default chain deliberately - the same mechanism an
  ECS/App Runner task role will use in Phase 10, so nothing here needs to
  change before deployment. Just worth knowing that "healthy" today reflects
  whatever AWS identity happens to be ambient on this machine, not one
  scoped to `hrb_chatbot_v2`.
- [x] **Phase 10 (Claude Code) — Docker + AWS deployment via App Runner.**
  Target chosen over ECS Fargate (simpler for one container, no ALB/task-def
  to hand-wire) and over AgentCore Runtime (per the earlier confirmed
  decision). Deploying under the same ambient AWS identity Phase 9 found
  (`BedrockAgentCore` user, account `418884736369`, region `us-east-1`) -
  confirmed via `aws sts get-caller-identity` / `iam list-attached-user-policies`
  that this identity holds `AdministratorAccess` and the account already
  hosts unrelated projects (`ai-workflows/vacation-planner-*` in ECR,
  `us-east-2`) - not a project-dedicated account, the user's own general
  sandbox, used deliberately with informed consent.

  **Real resource identifiers - write these down, they're useless from memory:**
  | What | Value |
  |---|---|
  | ECR repository | `418884736369.dkr.ecr.us-east-1.amazonaws.com/hrb-chatbot` |
  | Access role (App Runner → ECR pull) | `arn:aws:iam::418884736369:role/hrb-chatbot-apprunner-access-role` |
  | Instance role (the running app's own permissions) | `arn:aws:iam::418884736369:role/hrb-chatbot-apprunner-instance-role` - inline policies `bedrock-invoke-only` (`bedrock:InvokeModel`, `InvokeModelWithResponseStream`, `ListFoundationModels`) and `secrets-manager-read-own` (`secretsmanager:GetSecretValue` on `hrb-chatbot/*` only) - deliberately **not** the admin identity that deployed it |
  | Secrets (Secrets Manager, `us-east-1`) | `hrb-chatbot/OPENAI_API_KEY`, `hrb-chatbot/ANTHROPIC_API_KEY`, `hrb-chatbot/OPENROUTER_API_KEY`, `hrb-chatbot/TAVILY_API_KEY`, `hrb-chatbot/PINECONE_API_KEY` - created by `create_secrets.py` (a scratchpad script, not in the repo) reading `.env` directly, values never echoed anywhere |
  | App Runner service (final, running) | `arn:aws:apprunner:us-east-1:418884736369:service/hrb-chatbot/f957548202f343aa8ca91f341d71d85a` → `https://mrgysvt6ye.us-east-1.awsapprunner.com` |
  | GitHub Actions deploy user (Phase 11) | IAM user `hrb-chatbot-github-actions-deploy` - static access key, stored only in this repo's GitHub Actions secrets (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`), scoped to push `hrb-chatbot` ECR images and call `apprunner:StartDeployment`/`DescribeService` on this one service only |

  **A real code change landed as part of this phase** (not just config):
  `documents_service.py`, `ai/doc_processing/indexing/vector_indexer.py` and
  `api/rag/routes_documents.py` all called `db_gateway.sqlite()` directly,
  with no config switch - unlike the vector store, the metadata store had
  no equivalent of `RAG_VECTOR_DB`. This surfaced because App Runner has no
  persistent local disk (same problem `docs/S3-ASYNC-UPLOAD-DESIGN.md`
  already documented for Lambda) - SQLite silently wiped on every restart
  would have been discovered by *deploying*, not by anyone reading the code.
  Added `db_gateway.metadata_store(provider=None)` reading a new
  `RAG_METADATA_STORE` setting (`sqlite` default, matches local dev
  unchanged; `postgres` for anywhere without persistent disk), and switched
  all three call sites to it. `documents_service.py`/`vector_indexer.py` are
  Claude-Code-owned per the seam table above, so this was in-scope to fix
  without asking - the hand-written `ai/rag_pipeline/` layer was untouched.

  **Decided, with the user, before spending anything:**
  - App Runner over ECS Fargate (see above).
  - Deployed backends are **Pinecone (vector) + Postgres (metadata)**, not
    the local defaults (chromadb+sqlite) - both already fully implemented
    (Phases 2.5/2.6), both remote, both survive an App Runner restart.
  - Postgres reachability: **hosted Postgres (Neon)**, not Amazon RDS - RDS
    would need a DB subnet group, a security group, and an App Runner VPC
    Connector just to reach a VPC; Neon is a plain reachable connection
    string, same `postgres_client.py` code, zero networking to wire up.
  - Secrets via **AWS Secrets Manager**, not plaintext App Runner
    environment variables - the instance role can read only the
    `hrb-chatbot/*` secrets, nothing else in the account.
  - AWS CLI here was `aws-cli/2.0.30` (~2020), missing `apprunner` and other
    modern subcommands entirely - user chose to upgrade it (see below)
    rather than script around it forever; deployment itself was done via a
    `boto3` script regardless, since `boto3` in the project's venv (1.43.89)
    already supports App Runner independent of the CLI's own version.

  **What's actually done, verified live against the real deployed URL:**
  - [x] ECR repo created, image built locally and pushed as `:latest`.
  - [x] Both IAM roles created with scoped (non-admin) policies.
  - [x] Five secrets created in Secrets Manager from `.env`'s current keys.
  - [x] `RAG_METADATA_STORE` switch added and wired through all three call sites.
  - [x] App Runner service `RUNNING` - confirmed via `GET /health` (`200`,
    `"status":"healthy"`), `GET /health?deep=true` (`200`, real OpenAI call,
    127 models visible - proves `OPENAI_API_KEY` resolved correctly from
    Secrets Manager), and `GET /health?deep=true&vector_provider=pinecone`
    (`200`, real Pinecone call, `total_vector_count: 45` - the same 45
    chunks indexed during local testing, since Pinecone is the one shared
    persistent backend both environments point at).

  **Three real bugs, not one, across four deploy attempts - each found by
  deploying and reading logs, not by reasoning about the config beforehand:**
  1. **Secret ARNs hand-typed without their random suffix.** Secrets Manager
     appends one to every secret name; App Runner's `RuntimeEnvironmentSecrets`
     requires the exact full ARN, and silently produces `CREATE_FAILED` (image
     pulls fine, container never starts, zero application-level logs) rather
     than a validation error naming the real problem. Fixed by resolving ARNs
     via `secretsmanager.list_secrets` at deploy time instead of ever
     constructing one by hand again.
  2. **BuildKit's default provenance/SBOM attestation manifests.** `docker
     build` (no flags) pushes an OCI image *index* wrapping the real image
     plus an attestation manifest - a well-documented cause of exactly this
     "pulls fine, silently fails to start" symptom across AWS services
     (Lambda has the identical documented issue). Fixed with
     `--provenance=false --sbom=false`.
  3. **OCI-format manifest, not classic Docker v2 schema2, even with
     attestations off.** `docker manifest inspect` on the pushed image still
     showed `mediaType: application/vnd.oci.image.manifest.v1+json` after
     fix #2 - App Runner needs `application/vnd.docker.distribution.manifest.v2+json`.
     Fixed with `docker buildx build --output type=image,...,oci-mediatypes=false,push=true`,
     verified by re-running `docker manifest inspect` and confirming the
     media type changed *before* spending another ~9-minute AWS deploy cycle
     finding out the hard way.

  All three fixes are load-bearing in `.github/workflows/deploy.yml` now
  (Phase 11) - the build step's three flags are commented there specifically
  so a future edit doesn't drop one back out.

  **Known, deliberate, temporary compromise in the deployed config:**
  `RAG_METADATA_STORE=sqlite` in the App Runner service's own environment
  variables right now - the *ephemeral* option - because Neon didn't exist
  yet when the service was created and App Runner refuses to start a
  service whose `RuntimeEnvironmentSecrets` reference a secret ARN that
  doesn't exist. `RAG_VECTOR_DB=pinecone` is already live and persistent.
  Once Neon exists, finishing this is: create 5 more secrets
  (`hrb-chatbot/POSTGRES_DB_HOST/PORT/NAME/USER/PASSWORD` - the instance
  role's `hrb-chatbot/*` policy already covers them, no IAM change needed),
  then call `apprunner.update_service` flipping `RAG_METADATA_STORE` to
  `postgres` and adding those 5 to `RuntimeEnvironmentSecrets`. No image
  rebuild needed - this is config-only.

  **Known, deliberate, temporary compromise in the deployed config:**
  `RAG_METADATA_STORE=sqlite` in the App Runner service's own environment
  variables right now - the *ephemeral* option - because Neon didn't exist
  yet when the service was created and App Runner refuses to start a
  service whose `RuntimeEnvironmentSecrets` reference a secret ARN that
  doesn't exist. `RAG_VECTOR_DB=pinecone` is already live and persistent.
  Once Neon exists, finishing this is: create 5 more secrets
  (`hrb-chatbot/POSTGRES_DB_HOST/PORT/NAME/USER/PASSWORD` - the instance
  role's `hrb-chatbot/*` policy already covers them, no IAM change needed),
  then call `apprunner.update_service` flipping `RAG_METADATA_STORE` to
  `postgres` and adding those 5 to `RuntimeEnvironmentSecrets`. No image
  rebuild needed - this is config-only.

  **Blocked on the user, not on Claude Code:** a free Neon Postgres
  project/database - sign up at neon.tech, create one, and either paste the
  connection details in chat (never echoed back, same handling as every
  other key in this project) or note them somewhere I can read directly.

  **AWS CLI upgrade** (`winget upgrade --id Amazon.AWSCLI`, 2.0.30 → 2.36.40):
  appeared stuck at "Starting package install..." for several minutes with
  no further output (assumed blocked on a UAC prompt this non-interactive
  shell can't answer) - but it had actually completed in the background;
  `aws --version` later confirmed `2.36.40`. Worth remembering: a
  long-silent background command here isn't necessarily stuck, and is
  worth checking again before working around it with something slower.

  **Not yet done:** CloudWatch log group verification (App Runner creates
  one automatically per service - not yet confirmed it's receiving this
  app's `structlog`/`loguru` output correctly), a custom domain (not
  requested), and any autoscaling configuration beyond App Runner's default.
- [x] **Phase 11 (Claude Code) — CI/CD + GitHub.**
  `.github/workflows/ci.yml` (every push/PR, any branch, no AWS credentials
  at all - import smoke test + Docker build validation) and
  `.github/workflows/deploy.yml` (push to `main` only - builds with the
  same three flags Phase 10 found were load-bearing, pushes to ECR, calls
  `apprunner start-deployment`). `.githooks/pre-commit` content-scans staged
  diffs for real API key shapes before allowing a commit - opt in with
  `git config core.hooksPath .githooks`.

  **CI verified for real, not just committed:** pushed to `hrb_rag_pipelines`
  (commit `00b7be8`) and polled the GitHub Actions API directly -
  [run 34184448804](https://github.com/rvsree/hrb_chatbot_v2/actions/runs/34184448804)
  completed `success` on both jobs (`App imports cleanly`, `Docker image
  builds`).

  **Deploy (`deploy.yml`) is written but not yet exercised** - it only
  triggers on `main`, which is still empty on the remote (nothing merged
  there yet, unchanged from before this phase). Two things need to happen
  before it can run for real:
  1. **Blocked on the user:** the two GitHub Actions secrets
     (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` for the
     `hrb-chatbot-github-actions-deploy` IAM user) still need to be added
     via GitHub's own UI (Settings → Secrets and variables → Actions) -
     the values are sitting in a local, un-committed scratch file
     (`github_actions_credentials.txt`, never printed to any tool output
     or chat message) specifically so they could be copied in without ever
     appearing in this conversation. **Delete that file once copied in.**
  2. A merge (or push) to `main`.

  **Why a static IAM user instead of GitHub's OIDC (no long-lived keys)**:
  the OIDC setup (an account-wide identity-provider trust relationship) was
  blocked by Claude Code's own safety classifier and needed explicit
  sign-off; offered as a choice, the user chose the static-key IAM user
  instead, accepting a long-lived key in GitHub Secrets in exchange for a
  simpler one-time setup - deliberate, not a fallback taken silently. The
  user is still scoped tightly (ECR push to this one repo, App Runner
  deploy-trigger on this one service only), same principle as every other
  role in Phase 10, just not the zero-static-secret ideal.

  **A bug in the hook itself, caught by testing it, not by writing it
  carefully:** the first version's key-shape regex (`sk-[A-Za-z0-9]` with
  no minimum length) matched *inside ordinary English words*
  ("ta`sk-d`ef" in this very file) and blocked an unrelated commit. The fix
  that added a length minimum then went too far the other way - it
  forbade `-`/`_`, which real base64url key material actually contains, so
  it stopped matching real keys at all. Both were only found by testing the
  hook against realistically-shaped fake keys for all five providers before
  trusting it - reasoning about the regex alone missed both.

- [x] **Phase 12 (Claude Code) — REST API contract-first hardening.**
  Requested directly: versioning, idempotency, rate limiting, request
  validation bounds, graceful error handling, structural guardrails, a
  centralized validation point, and pre-flight backend-readiness checks
  before spending money - implemented for real, not just discussed, and
  documented in depth in `docs/FAQ.md`'s section 6.

  **Versioning**: every business endpoint now under `/v1`
  (`main.py`'s `include_router(..., prefix="/v1")`); `GET /health`
  deliberately stays unversioned, matching how a liveness/readiness probe
  is conventionally exempted from an API's own version scheme.

  **Idempotency**: `common/idempotency/idempotency_store.py`, an
  `Idempotency-Key` header (Stripe's own convention) on upload/index/query.
  Verified live, not just unit-tested: uploading the same PDF twice with
  the same key returns the *same* `document_id` both times.

  **Rate limiting**: `common/rate_limiting/rate_limiter.py`, fixed-window,
  per-client-IP, applied via `Depends(enforce_rate_limit)` to every
  endpoint that writes state or spends money. Finally gives
  `APP_RATE_LIMITING`/`APP_RATE_LIMIT_REQUESTS`/`APP_RATE_LIMIT_DURATION` a
  real job - orphan `.env` config since this project's first commit (see
  `docs/BACKLOG.md`).

  **Request validation**: an audit found `RagQueryRequest.query` had a
  `min_length` but no `max_length` at all - fixed with a 2000-character
  cap, plus matching bounds on `vector_db`/`model_name`/`embedding_model`.

  **Error handling**: the same audit found two `json_error(...)` calls
  interpolating a caught exception's raw `str(error)` directly into the
  client-facing message - a real info-leak risk. Both now log full detail
  server-side and return a generic message. `main.py` also gained a global
  `@app.exception_handler(Exception)`, confirmed absent before this.

  **Pre-flight check before spending money**: `index_document()` now
  checks (shallow, free) that the LLM provider and vector store are
  configured before attempting the real pipeline call, returning a clean
  503 instead of a raw exception deep in the stack. **Deliberately not**
  applied to the query endpoint - it's still a pure stub, and gating it
  behind a real API key would break in CI, which runs with zero secrets
  (see `docs/AWS-DEVOPS-RUNBOOK.md`) - add the same check there once
  Phase 6 makes a real call.

  Both single-process, in-memory limitations (idempotency, rate limiting)
  are documented in their own modules' docstrings, not a surprise to
  discover later - a real shared store (Redis) is the fix the moment this
  app ever runs as more than one instance.

Explicitly deferred to a later, separate wave - not part of the above:
**ReAct multi-agents, MCP tools, caching.**

- [x] **Phase 2.5 (Claude Code, added on request) — Postgres, fully implemented.**
  `postgres_client.py` rewritten from a stub to a real implementation of the
  same `BaseMetadataClient` contract as `sqlite_client.py` - not the active
  store (SQLite still is, in `documents_service.py`), but genuinely working
  and checkable on its own via `GET /health?deep=true&metadata_provider=postgres`.

  Two real things found and fixed while building this, not glossed over:
  - **`.env`'s Postgres credentials pointed at `hrb_emp_assist`'s own shared
    database** (`hr_chatbot` - confirmed by listing its tables:
    `employees`, `leave_requests`, `chat_history`, etc.). Asked the user
    before touching it; created a dedicated `hrb_chatbot_v2` database on the
    same local Postgres server instead, and updated `POSTGRES_DB_NAME` in
    `.env` to point at it. This project's data can no longer collide with
    or be confused for the other project's.
  - **psycopg's native async driver (`AsyncConnection`) does not work on
    Windows** under the default `ProactorEventLoop` - raises
    `InterfaceError` on connect. Fixed by running ordinary synchronous
    psycopg calls inside `asyncio.to_thread()`, the same strategy
    `aiosqlite` itself uses internally (sqlite3 has no async driver
    either). Portable to the Linux deployment target too, not a
    Windows-only patch.

  Verified live: `create_document`, `get_document`, `update_status`,
  `list_documents` all tested directly against the real `hrb_chatbot_v2`
  database (not mocked), including the unknown-id case; `GET
  /health?deep=true` confirmed both `metadata_provider=sqlite` (6 real
  documents) and `=postgres` (0, its own clean database) report healthy
  independently.

- [x] **Phase 2.6 (Claude Code, added on request) — Pinecone, fully
  implemented**, once the user created a real account and added
  `PINECONE_API_KEY` to `.env`. `pinecone_client.py` rewritten from stub to
  real, implementing `BaseVectorDBClient` - not the active store (ChromaDB
  still is), checkable on its own via
  `GET /health?deep=true&vector_provider=pinecone`.

  Design decisions worth knowing before writing retrieval code against
  either backend:
  - **`collection_name` maps to a Pinecone namespace**, not a separate
    index - one `PINECONE_INDEX_NAME` is configured for this whole client,
    since a Pinecone index has one fixed vector dimension for everything in
    it.
  - **Pinecone has no native "documents" field.** The raw chunk text is
    stored under a `"document"` metadata key on upsert and extracted back
    out on query, to keep the same shape `ChromaDBClient.query()` returns.
  - **The score/distance inversion is real and not silently corrected.**
    Chroma's `"distances"` are lower-is-better; Pinecone's are a cosine
    *similarity* score, higher-is-better. Both are returned under the same
    `"distances"` key for shape-compatibility, but the number means the
    opposite thing depending on which backend answered - documented
    prominently in `pinecone_client.py`'s module docstring, not papered
    over with a guessed transform.
  - **`.env`'s placeholder index name (`hrb_benefits_index_name`) would
    have been rejected outright** - Pinecone index names allow only
    lowercase letters, digits and hyphens, no underscores. Corrected to
    `hrb-chatbot-kb` while filling in the rest of the Pinecone settings
    (`PINECONE_CLOUD`, `PINECONE_ENVIRONMENT`, `PINECONE_METRIC`,
    `PINECONE_DIMENSION`).

  Verified live, against the real account: `GET /health?deep=true&vector_provider=pinecone`
  created the `hrb-chatbot-kb` serverless index on first call (confirmed
  `index_already_existed: false`, then `true` on the next call); a direct
  upsert/query/delete test with two fake chunks confirmed the exact chunk
  queried came back first with the highest score (~0.9999997), the other
  chunk scored lower (~0.748), document text and metadata round-tripped
  correctly, and `total_vector_count: 0` after delete confirmed cleanup.
  Also confirmed the shallow check (`vector_provider=pinecone`, no
  `deep=true`) makes no network call at all - unlike ChromaDB, Pinecone is
  a real external service, so this matters.

- [x] **Phase 13 (Claude Code, added on request) — Branch restructuring +
  CI/CD gates.** Requested directly: create `develop`/`feature`/`master`-
  style branches, commit current work to a new feature branch, and design
  the ongoing testing/release process for future feature areas (a ReAct
  multi-agent setup, MCP workflows, conversation memory, session/state
  caching - the items explicitly deferred at the end of Phase 12 above).

  **Branches created**, cut from `hrb_rag_pipelines` at commit `416f977`:
  `main`, `developer`, `feature`, `feature-kb-indexing-rag-pipeline`. The
  user then renamed three of them on GitHub's own UI - `main` → `master`,
  `developer` → `develop`, `feature-kb-indexing-rag-pipeline` →
  `feature-langchain-rag-pipeline` - and deleted the generic `feature`
  parent branch. **A GitHub rename deletes the old ref outright, no
  redirect** - confirmed via `git fetch --prune` showing all three old
  names as `[deleted]` - which meant `deploy.yml`'s `on: push: branches:
  ["main"]` and `ci.yml`'s `pull_request: branches: ["main"]` were now
  triggers pointing at nothing. Both fixed to `master` in the same change;
  missing this would have left `deploy.yml` silently dead (no error, it
  simply never fires) the next time anyone pushed expecting it to deploy.

  **CI/CD gates measured before being set, not guessed** - the same
  lesson twice in one sitting:
  - A first attempt at a coverage floor used `--cov-fail-under=70` before
    ever running it for real. Actually running it: **46%** measured. Set
    to `--cov-fail-under=45` instead - a ratchet with real headroom, not a
    number that would have broken the very next CI run on code nobody
    had touched.
  - A first attempt at `pip-audit` let it fail the job on any CVE found.
    Running it for real turned up dozens of pre-existing CVEs across
    `langchain*`/`chromadb`/`starlette`/`pillow` - versions pinned for
    compatibility long before this scan existed. Set to
    `continue-on-error: true` (report-only) instead, with a documented
    triage plan before flipping it to blocking - see `docs/BACKLOG.md`'s
    new CI/CD section.
  - `bandit -ll` (static security analysis) *is* enforced as blocking -
    it ran clean (zero MEDIUM+ findings) against the real codebase, so
    unlike the two above, this one didn't need a lowered bar.

  **Deployment testing added to `deploy.yml`**: `aws apprunner
  start-deployment` only starts a deployment and returns almost
  immediately - two new steps after it actually confirm the deploy
  worked: poll `describe-service` until `Service.Status` is `RUNNING`
  (5-minute timeout, fails the job on anything else), then a real `curl
  --fail` against the live URL's `/health`. Previously, a deployment that
  "succeeded" by AWS's own accounting but produced a container that never
  came up would have left GitHub Actions reporting green.

  **New doc**: `docs/CICD-BRANCHING-STRATEGY.md` - the branch-role table,
  every gate and its threshold with the reasoning behind each number, the
  wheel-vs-JAR packaging question answered directly (a wheel isn't added;
  the Docker image already is this project's versioned deployable
  artifact - see that doc for the full reasoning and what *would* justify
  adding one), and an honest two-option write-up on whether `develop`
  should get its own staging App Runner deployment (real ongoing AWS
  cost either way) - **left as an open decision, not built without being
  asked**, same category of call as the Neon Postgres signup already
  tracked in `docs/HANDOFF.md`.

  **Not done, flagged rather than silently skipped**: the GitHub repo's
  default branch is still `hrb_rag_pipelines`, not `master` (a Settings →
  Branches action); no branch-protection rules exist yet requiring CI to
  pass before a merge into `develop`/`master`; Docker images are still
  tagged `:latest` only, with no per-SHA tag to roll back to if a deploy
  passes its own health check but is broken some other way - deliberately
  not touched in this same pass, since `deploy.yml`'s build command has
  caused three real failures before (see "Three real bugs found the hard
  way" in `docs/AWS-DEVOPS-RUNBOOK.md`) and earns its own isolated test
  before being changed again.

- [x] **Phase 14.1 (Claude Code, on request 2026-09-13) — Idempotency
  removed.** User decision, made explicitly during a much longer
  discussion about replacing the hand-rolled chunking/indexing/retrieval
  code with direct LangChain (chunking, retrieval/generation) and
  LlamaIndex (indexing) usage instead - see Phase 14.2 below for that
  larger, separate effort. Idempotency was called out by name as one of
  the "complex optional" pieces to drop for now, to be revisited later,
  not a verdict on whether it's worth having.

  All three mechanisms removed, not just the one literally named
  "idempotency": the `Idempotency-Key` header cache
  (`common/idempotency/idempotency_store.py`, on upload/index/query), the
  SHA-256 content-hash duplicate-upload check
  (`documents_service.save_upload()`'s `find_by_content_hash()` call), and
  their dedicated tests
  (`tests/hrb_chatbot/common/idempotency/test_idempotency_store.py`,
  `tests/hrb_chatbot/api/rag/test_idempotency_and_rate_limiting.py`). The
  third mechanism this project's own idempotency terminology never
  actually named - `vector_indexer.py`'s deterministic chunk ids
  (`{document_id}:{chunk_index}`, making a re-index an upsert rather than
  a duplicate insert) - was deliberately left alone here; it will be
  superseded naturally once Phase 14.2's LlamaIndex rewrite replaces
  `vector_indexer.py` outright, not worth touching twice.

  Behavior change: uploading identical content now always creates a new
  document (`status: "uploaded"`, a fresh `document_id`) instead of being
  detected as a `"duplicate"` of the existing one. `content_hash` is
  still computed and stored on each document row (harmless, no schema
  change needed), just no longer checked against on upload.

  Verified: full test suite green (73/73) after the change, including two
  rewritten tests in `test_routes_documents.py` that used to assert
  duplicate-detection and now assert two independent documents are
  created from identical content instead. `README.md`, `README_TEST.md`,
  `docs/FAQ.md`, `docs/HANDOFF.md`, `docs/BACKLOG.md` updated to match -
  `BACKLOG.md`'s idempotency line is deliberately un-struck-through
  (back on the backlog as a real gap, not deleted from the project's
  history of having built it once already).

  **Planned re-implementation**: a real shared store (Redis), not the
  same single-process in-memory cache - the fix already named as the
  eventual next step even before removal, see the limitation noted in the
  now-deleted module's own docstring and quoted throughout the docs
  above. No timeline yet; picked up whenever the pipeline rewrite below
  is stable.

- [ ] **Phase 14.2 (Claude Code, in progress 2026-09-13) — Replace the
  hand-written chunking/indexing/retrieval pipeline with direct
  LangChain + LlamaIndex usage, mirroring
  `support_desk_rag_workshop/SupportDesk-RAG-Workshop`'s modules
  directly** (not reimplemented natively - the explicit point of this
  phase is to stop hand-rolling what these libraries already do, per the
  user's direct correction after an earlier, wrong assumption otherwise).
  Framework split matches the workshop's own module split: **LangChain**
  for chunking (module 2) and the retrieval/generation pipeline
  (module 4); **LlamaIndex** for indexing (module 3) - a library this
  project has not used before now.

  **Chunking** (`ai/doc_processing/chunking/`) - six techniques as plain
  functions (no classes/interfaces, mirroring `demo.py`'s own style, per
  the user's explicit "coming from a Java background, keep the Python
  simple" instruction): fixed-size (`CharacterTextSplitter`), recursive
  (`RecursiveCharacterTextSplitter`, the default), semantic
  (`SemanticChunker`), markdown-aware (`MarkdownHeaderTextSplitter`),
  HTML-aware (`HTMLHeaderTextSplitter`), and whole-document/none. Each
  technique gets its own dedicated endpoint
  (`POST /v1/rag-ingestion/documents/{id}/index/<strategy>`) *and* the
  existing endpoint gains an optional `chunking_strategy` field for
  dynamic selection - both call the same underlying function. When not
  specified explicitly, a small pre-processing function auto-selects
  using rules sourced directly from the workshop's own
  `modules/2_chunking/notes.md` decision matrix (markdown headers →
  markdown; HTML tags → html; shorter than one chunk → none; otherwise →
  recursive) - `semantic` is never auto-selected, since the workshop ties
  it to "when accuracy is critical," not something detectable from the
  text itself.

  **Indexing** (`ai/doc_processing/indexing/`) - rebuilding
  `vector_indexer.py` on LlamaIndex's `VectorStoreIndex` (user's explicit
  choice over leaving the current raw-SDK version untouched), against
  **both** ChromaDB and Pinecone (both already-configured backends kept,
  per user request - not narrowing to one). MVP scope is Vector Index
  only; Summary/Tree/Keyword-Table/Hybrid indexing (all demonstrated in
  workshop module 3) are explicitly **deferred**, documented here rather
  than built now, since Tree/Keyword/Hybrid need a second storage
  structure beyond a flat vector index (an inverted keyword table, a
  hierarchical summarized-node tree) that doesn't fit the current
  `BaseVectorDBClient` contract - a bigger, separate design effort once
  this MVP is stable.

  **Search/retrieval** (`ai/rag_pipeline/query_retrieval/`) - rebuilding
  the vector-store layer end-to-end on LangChain's `Chroma`/Pinecone
  vectorstore wrappers (user's explicit choice over a smaller
  search-path-only change), reading the same collection/index
  LlamaIndex's indexing side writes to. MVP scope is Similarity (the
  existing default behavior) and MMR only; score-threshold-gated
  fallback and multi-turn query reformulation (both already implemented
  today in the current hand-written `retriever.py`/`pipeline.py`, and
  also present in workshop module 4) are carried forward as-is for now,
  not rebuilt in this pass. Default when `search_strategy` isn't given
  explicitly stays similarity, unchanged from today; MMR is opt-in via
  the field or a dedicated `POST /v1/rag-retrieval/query/mmr` endpoint.

  **Logging**: plain `logging.info(...)` lines at each selection point
  (explicit vs. auto-selected strategy, which one, for which document/
  query) - no structured/JSON logging, no tracing library, per the same
  "keep it simple" instruction as the chunking style above.

  **Chunking sub-phase done, 2026-09-13** - `text_chunker.py` rewritten on
  the six LangChain functions described above; `pipeline.py`'s
  `chunk_document()`/`index_document()` take an optional
  `chunking_strategy`, resolve and log it whether explicit or
  auto-selected, and report it back in `IndexResponse.chunking_strategy`
  (`models/documents.py`). New deps installed and pinned in
  `requirements.txt`: `langchain-text-splitters==0.3.11` (already a
  transitive dep, now imported directly), `langchain-experimental==0.3.4`
  (`SemanticChunker` only), `beautifulsoup4==4.12.3`
  (`HTMLHeaderTextSplitter`'s own runtime dependency, not imported
  directly - its absence surfaced as a live `ImportError` from inside
  `langchain_text_splitters/html.py` while testing, not predicted in
  advance). `routes_documents.py` gained
  `POST /v1/rag-ingestion/documents/{id}/index/{chunking_strategy}` (one
  dedicated URL per technique, an unknown strategy segment returns `404`)
  alongside the existing endpoint's new optional field - both call one
  shared `_index_document()` helper, no duplicated route logic.

  Existing chunking tests rewritten, not just patched - two of the four
  original tests asserted specific-to-the-old-hand-rolled-algorithm
  invariants that don't hold for LangChain's splitter (a zero-overlap-vs-
  real-overlap chunk-count ordering, and later a tail-substring overlap
  check that passed by coincidence on repeated sentence text rather than
  proving anything about overlap) - both replaced with more robust
  checks against unique, non-repeating text. 16 tests total now, covering
  all six strategies plus `decide_chunking_strategy()`'s four rules and
  explicit-vs-auto dispatch in `chunk_text()`. `semantic` has no test -
  it needs a real embedding call, same reasoning this project already
  applies elsewhere for keeping real API cost out of `pytest`.

  **Verified live, real cost incurred** (not just unit-tested): started
  the app with uvicorn, uploaded a real PDF
  (`JPMC Guild Tuition Assistance.pdf`), then in sequence -
  `POST .../index/recursive` → `action: "insert"`, 45 chunks,
  `chunking_strategy: "recursive"` in the response; `POST .../index` (no
  strategy) → `action: "update"`, auto-selected `"recursive"` again (same
  long plain-text PDF, so the same auto-selection rule applies both
  times), 45 chunks unchanged; `POST .../index/none` → `action: "update"`,
  1 chunk, `chunks_removed: 44` (stale-chunk cleanup still works
  correctly against a real backend); `POST .../index/markdown` → 1 chunk
  (no markdown headers in PDF-extracted text, so the whole document comes
  back as one chunk - correct, not an error); `POST .../index/not-a-real-
  strategy` → `404`. Confirmed the log lines read consistently at every
  step (`chunking_strategy=recursive`/`auto` at the pipeline level,
  `chunking: explicit/auto-selected strategy=...` at the chunker level) -
  an earlier version of this logging showed `chunking_strategy=auto`
  immediately followed by `chunking: explicit strategy=recursive`, which
  was real but confusing: `pipeline.py` was resolving the strategy before
  passing it down, so the chunker never saw that it had been auto-picked.
  Fixed by passing the original (possibly `None`) value down unchanged,
  and computing the resolved value again, separately, only for the
  response - `decide_chunking_strategy()` is pure/deterministic, so this
  costs one cheap extra call, not a second real decision that could
  disagree with the first. Test document deleted afterward, full suite
  green (84/84) throughout.

  **Indexing sub-phase done, 2026-09-13** - `vector_indexer.py` rebuilt on
  LlamaIndex's `VectorStoreIndex` (`llama_index-core==0.13.6`,
  `llama-index-vector-stores-chroma==0.6.0`,
  `llama-index-vector-stores-pinecone==0.9.0`,
  `llama-index-embeddings-openai==0.7.0` - the last one installed but not
  actually used: embeddings stay Module-1/`embedding_generator.py`'s own
  explicit step, pre-computed and attached directly to each `TextNode` via
  `embedding=`, not delegated to LlamaIndex's own embed model - narrower
  scope than the workshop's `Settings.embed_model` pattern, deliberately,
  since only indexing was asked for this sub-phase). Only the "write new
  chunks in" step goes through LlamaIndex
  (`VectorStoreIndex.insert_nodes()`); stale-chunk deletion and the
  supersede-flip stay this project's own logic via the same
  `BaseVectorDBClient.delete()`/`update_metadata()` calls as before - see
  `vector_indexer.py`'s own module docstring for why splitting it that way
  made sense. Against **both** ChromaDB and Pinecone, per user request -
  not narrowing to one.

  **Dependency conflicts, resolved and verified, not just accepted
  blindly**: installing `llama-index-core` forced `pydantic` 2.9.2 → 2.13.5
  and (via `llama-index-vector-stores-pinecone`) `pinecone` 10.0.0 → 9.1.0
  - a real downgrade of an already-working client. Both verified live
  before being accepted: full suite green (84/84) after the pydantic bump;
  `GET /health?deep=true&vector_provider=pinecone` still reports healthy
  with the correct `total_vector_count` after the pinecone downgrade -
  `pinecone_client.py` only uses core `Pinecone`/`ServerlessSpec`/`Index`
  APIs, stable across this version range.

  **Three real integration bugs found live, none guessable from reading
  LlamaIndex's docs alone - all found by writing a real chunk and
  inspecting exactly what got stored, not by reasoning about the library
  in the abstract:**

  1. **`document_id` metadata collision.** Passing `document_id` as a
     plain key in `TextNode.metadata` seemed like the obvious approach -
     it silently came back as the literal string `"None"` on every stored
     chunk instead. Root cause: LlamaIndex's `node_to_metadata_dict()`
     (used by both the Chroma and Pinecone integrations) reserves the
     metadata keys `document_id`/`doc_id`/`ref_doc_id` for its own use,
     derived from the node's `SOURCE` relationship (`node.ref_doc_id`) -
     and overwrites a same-named custom field with that derived value,
     unset if the relationship was never set. Fixed by never putting
     `document_id` in `node.metadata` at all; setting
     `node.relationships[NodeRelationship.SOURCE] =
     RelatedNodeInfo(node_id=document_id)` instead makes LlamaIndex
     populate `document_id`/`doc_id`/`ref_doc_id` correctly, with the real
     value - confirmed by direct `collection.get()` against a real
     ephemeral Chroma collection before touching any real data.

  2. **Pinecone-only id prefixing breaks every subsequent delete/update.**
     Setting that same `SOURCE` relationship (needed for bug #1's fix) has
     a Pinecone-specific side effect: `PineconeVectorStore.add()` (read
     directly from its installed source,
     `llama_index/vector_stores/pinecone/base.py`) prefixes every stored
     id with `f"{ref_doc_id}#"` whenever a node has one - Chroma's
     integration does not do this. Confirmed live against the real index:
     a chunk written as `document_id:chunk_index` was actually stored as
     `document_id#document_id:chunk_index`; fetching the plain id found
     nothing, the prefixed id found it. Worse: LlamaIndex's own
     `delete_nodes(node_ids=...)` does **not** reverse this prefix either
     - it passes whatever ids it's given straight through to Pinecone's
     `delete()`. Left unfixed, this would have made stale-chunk cleanup,
     whole-document delete, and the supersede-flip all silently no-op
     against Pinecone specifically (Pinecone doesn't error on deleting a
     nonexistent id) - orphaned vectors accumulating forever with no
     visible failure anywhere. Fixed with a new `storage_chunk_ids()`
     function (backend-name-branched, same style as
     `retriever.py`'s existing `_meets_relevance_bar()`) that computes the
     *actually-stored* id for a delete/update call, used at all three
     call sites: `vector_indexer.py`'s stale-chunk delete and
     supersede-flip, and `documents_service.py`'s whole-document delete
     (which needed the same fix, and the same new import).

     **Verified live against the real Pinecone index, not just logically
     reasoned through**: re-indexed a real 55-chunk document with a
     larger `chunk_size` (forcing a shrink to 13 chunks) -
     `total_vector_count` dropped by exactly 42 (matching the reported
     `chunks_removed`), and the specific stale prefixed id was confirmed
     gone via a direct `fetch()`; then deleted the whole document - count
     returned to exactly the pre-test baseline (45), confirming the
     delete path is fixed too. The supersede-flip fix uses the identical
     `storage_chunk_ids()` call already proven correct at the other two
     sites, but wasn't separately live-tested with its own two-document
     supersede scenario in this pass - flagged here rather than silently
     assumed.

  3. **Pinecone chunk text goes missing for existing (old) retrieval
     code.** LlamaIndex's `PineconeVectorStore` doesn't write chunk text
     under this project's own `"document"` metadata key (`pinecone_client.py`'s
     established convention, since Pinecone has no native text field) -
     it lives inside a `"_node_content"` JSON blob LlamaIndex writes for
     its own use instead. Confirmed live: a real query against
     Pinecone-indexed content returned the *correct* `document_id`/
     `filename`/`score` for its top matches (proving the embeddings/
     similarity search side is fine) but `text: ""` for every one, so the
     LLM correctly - if unhelpfully - answered "I don't know" to a
     question its own retrieved chunks did cover. ChromaDB has no
     equivalent gap (chunk text is stored natively, separate from
     metadata, regardless of who wrote it). Rather than leave real
     retrieval broken until the search/retrieval sub-phase below lands,
     patched `pinecone_client.py`'s `query()` with a small, explicitly
     temporary fallback (`_text_from_llama_index_node_content()`) that
     parses `_node_content` for the text when `"document"` is empty -
     removable once `retriever.py` itself is rewritten on LangChain,
     since that rewrite won't go through this client's `"document"`
     convention at all. Verified live: the exact same query that returned
     `text: ""` before the fix returned the correct chunk text and a
     correct, grounded answer after it.

  **Tests**: the old `FakeVectorStore` (a plain in-memory dict, from
  `tests/conftest.py`, shared across much of the test suite) can no
  longer stand in for `write_chunks()`'s own tests - LlamaIndex's
  `ChromaVectorStore`/`PineconeVectorStore` need a real
  `chromadb.Collection`/`pinecone.Index` object, not something that only
  duck-types `BaseVectorDBClient`. Added `EphemeralChromaVectorStore` in
  `test_vector_indexer.py` itself (not `conftest.py`, kept scoped) - a
  real, in-memory `chromadb.EphemeralClient()` (zero network, zero cost,
  same reasoning this project already applies to keeping real API cost
  out of `pytest`), with a random per-instance collection-name suffix
  (needed because ephemeral clients turned out to still share collection
  storage by name within one test process - confirmed live: two tests
  using different embedding dimensions under the literal name
  `"hrb_chatbot_kb"` collided with a real `chromadb.errors.InvalidArgumentError`
  before this fix). All 7 existing tests adapted to read state from the
  real collection instead of a fake's own dict; one assertion added
  confirming `document_id` reads back correctly through the SOURCE-
  relationship fix (bug #1 above), not just that the call didn't crash.
  Full suite green (84/84) throughout.

  **Not done in this sub-phase**: the search/retrieval (LangChain)
  rewrite described above - next.

## Verification checklist (Phases 1-3)

1. `GET /health?deep=true` → vector + metadata database checks healthy. **Done.**
2. `POST /rag/documents` with a real PDF from `resources/kb_docs/` → 200,
   document id returned, file in `data/uploads/`, SQLite row exists. **Done**,
   including the batch partial-success case.
3. `POST /rag/documents/{id}/index` → clear `NotImplementedError` naming
   `ai/doc_processing/`, not a crash.
4. `POST /rag/query` → same stubbed-but-clear behavior, naming
   `ai/rag_pipeline/`.
