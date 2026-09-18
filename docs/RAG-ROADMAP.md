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

**`Spec` column, added 2026-09-14 when SDD was adopted** (see `CLAUDE.md`'s
SDD section): `Retrofitted (pre-SDD)` means the phase shipped before specs
were written first - its detail entry below is the historical record, not
reconstructed after the fact. `📋 pending` means no spec exists yet; one
must be written (`/spec-new`, or see `.claude/skills/spec-new/SKILL.md`) and
reviewed before that phase's code starts.

| Phase | Who | Status | Spec |
|---|---|---|---|
| 1 — ChromaDB client + gateway | Claude Code | ✅ Done | Retrofitted (pre-SDD) |
| 2 — Document upload API | Claude Code | ✅ Done | Retrofitted (pre-SDD) |
| 2.5 — Postgres metadata store | Claude Code | ✅ Done | Retrofitted (pre-SDD) |
| 2.6 — Pinecone vector store | Claude Code | ✅ Done | Retrofitted (pre-SDD) |
| 3 — Indexing trigger endpoint | Claude Code | ✅ Done | Retrofitted (pre-SDD) |
| 4 — Chunking/embedding/indexing | Claude Code (override) | ✅ Done | Retrofitted (pre-SDD) |
| 4.1 — Per-call config overrides | Claude Code (override) | ✅ Done | Retrofitted (pre-SDD) |
| 4.2 — Document metadata expansion + content-hash dedup | Claude Code (override) | ✅ Done, 2026-09-10 | Retrofitted (pre-SDD) |
| 4.3 — Delete endpoint | Claude Code (override) | ✅ Done, 2026-09-10 | Retrofitted (pre-SDD) |
| 4.4 — Document versioning (supersede + is_current retrieval filtering), table extraction, document-metadata extraction | Claude Code (override) | ✅ Done, 2026-09-11 | Retrofitted (pre-SDD) |
| 4.5 — Retrieval relevance threshold, standardized error codes | Claude Code | ✅ Done, 2026-09-11 | Retrofitted (pre-SDD) |
| 5 — Query endpoint, stubbed | Claude Code | ✅ Done | Retrofitted (pre-SDD) |
| 5.1 — Query decomposition | Hand-written | 📋 Planned | 📋 pending |
| 5.2 — Query variants | Hand-written | 📋 Planned | 📋 pending |
| 5.3 — Prompt chaining + versioning | Hand-written | 📋 Planned | 📋 pending |
| 6 — Retrieval + grounded generation | Claude Code (override, 2026-09-10) | 🚧 MVP done - real retrieval + generation, no COT/guardrails yet; see Phase 6 detail below | Retrofitted (pre-SDD) for the MVP shipped; the COT/guardrails remainder needs its own spec |
| 6.1 — Contracts/validation for query path | Claude Code | ✅ Done alongside the Phase 6 MVP - `model_used` added to `RagQueryResponse` | Retrofitted (pre-SDD) |
| 7 — Guardrails (input + output) | Hand-written | 📋 Planned | 📋 pending |
| 8 — Golden dataset + evaluations + A/B | Hand-written | 🚧 Golden dataset done (override, 2026-09-08); evaluations/A/B harness still 📋 planned | Retrofitted (pre-SDD) for the golden dataset; eval/A/B harness is 📋 pending |
| 9 — Bedrock as an LLM provider | Claude Code | ✅ Done | Retrofitted (pre-SDD) |
| 10 — Docker + AWS deployment (App Runner) | Claude Code | ✅ Done - `RUNNING`, verified live (shallow + deep health, real Pinecone query); Postgres/Neon leg still pending the user's Neon signup (documented compromise, not a blocker) | Retrofitted (pre-SDD) |
| 11 — CI/CD + GitHub | Claude Code | ✅ CI verified passing on GitHub Actions (pytest included as of Phase 12); deploy workflow written but unexercised - needs `main` merge + 2 GitHub Secrets still pending from the user | Retrofitted (pre-SDD) |
| 12 — REST API contract-first hardening | Claude Code | ✅ Done - versioning, idempotency, rate limiting, validation bounds, error handling, pre-flight checks, all verified live and unit-tested | Retrofitted (pre-SDD) |
| 13 — Branch restructuring + CI/CD gates | Claude Code | ✅ Done - `main`/`developer`/`feature-kb-indexing-rag-pipeline` renamed to `master`/`develop`/`feature-langchain-rag-pipeline` on GitHub; `deploy.yml`/`ci.yml` triggers fixed to match; coverage floor, `bandit`, `pip-audit`, and a real post-deploy smoke test added to CI/CD; see `docs/CICD-BRANCHING-STRATEGY.md` | Retrofitted (pre-SDD) |
| 14 — LangChain/LlamaIndex pipeline rewrite (chunking, indexing, search), idempotency removed | Claude Code | ✅ Done, on `feature-langchain-rag-pipeline`. All of 14.1 (idempotency removal) and 14.2 (chunking, indexing, search/retrieval sub-phases) complete | Retrofitted (pre-SDD) |
| 15 — Evaluation (Module 5) against the rebuilt pipeline | Claude Code | 📋 Planned, added 2026-09-13 - not started | 📋 pending - next candidate for `/spec-new` |
| 16 — Content-hash duplicate-upload detection, reinstated | Claude Code | ✅ Done, 2026-09-14 | ✅ Spec'd, reviewed, and implemented via the SDD process end to end - first phase to go through it - see detail below |
| 17 — Indexing write path standardized on LangChain's `index()`/`SQLRecordManager`, replacing LlamaIndex | Claude Code | ✅ Done, 2026-09-14 | ✅ Spec'd, reviewed (two real gaps found and resolved *during* implementation, not glossed over - see detail below), and implemented - see detail below |
| 18 — Chunking-strategy auto-selection: log the rationale, not just the result | Claude Code | ✅ Done, 2026-09-14 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 19 — Chunk-level metadata expansion (`doc_type`, `department`, new `doc_classification`) for filtering | Claude Code | ✅ Done, 2026-09-14 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 20 — MultiQueryRetriever + Self-Query Retriever | Claude Code | ✅ Done, 2026-09-14 | ✅ Spec'd, reviewed (real dependency deadlock found and resolved *during* implementation, and one real free-text-filter limitation found during live verification - both recorded, not glossed over - see detail below), and implemented - see detail below |
| 21 — Remove the duplicate per-strategy endpoints; one endpoint each for ingestion and retrieval | Claude Code | ✅ Done, 2026-09-14 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 22 — Comment-length cleanup across `src/hrb_chatbot/` + a codified 2-line rule | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 23 — FastAPI gateway layer: role-based access (RBAC) in front of RAG ingestion + retrieval, OAuth placeholder | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 24 — Fix: `validation_exception_handler` crashes on a malformed (non-JSON) body instead of returning a clean 422 | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 25 — Reindex by filename, not just `document_id` | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 26 — Simplify: one ingestion endpoint (upload+chunk+embed+store combined), separate index/reindex endpoint removed | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 27 — Delete-all-documents endpoint | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 28 — Fix: document_version reports 2 on a document's first-ever index | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 29 — Suppress misleading pdfminer FontBBox console warning | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 30 — Fix: running the test suite silently wiped the shared dev DB | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 31 — ACTIVE_VECTOR_DB/ACTIVE_LLM_PROVIDER .env vars, one resolver helper each | Claude Code | ✅ Done, 2026-09-15 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 32 — Pilot: one `RagQueryParams` dataclass replaces the 10-field parameter list repeated across routes_query.py/rag_service.py/pipeline.answer_query() | Claude Code | ✅ Done, 2026-09-16 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 33 — Remove dead pass-through wrapper functions in both pipeline.py files | Claude Code | ✅ Done, 2026-09-16 | ✅ Spec'd, reviewed, and implemented - see detail below |
| 34 — Simplify retrieve_chunks() to a single query; remove decompose_query() | Claude Code | ✅ Done, 2026-09-16 | ✅ Spec'd, reviewed, and implemented - see detail below |


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
  - **`ai/rag_pipeline/response_generation/response_generator.py`** - builds a
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
  metadata fallback, `top_k` limiting) and `response_generator.py` (no-chunks
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

  **Search/retrieval sub-phase done, 2026-09-13** - `retriever.py`
  rebuilt end-to-end on LangChain's own vector store wrappers
  (`langchain_chroma.Chroma`, `langchain_pinecone.PineconeVectorStore`,
  workshop Module 4), reading the exact same collection/namespace
  `vector_indexer.py`'s LlamaIndex writes into. Two plain functions -
  `search_similarity()` (the default) and `search_mmr()` - dispatched via
  a `SEARCH_STRATEGIES` dict, same pattern as `text_chunker.py`'s
  `CHUNKING_STRATEGIES`. Selection: an explicit `search_strategy` wins if
  given (new field on `RagQueryRequest`, and a dedicated
  `POST /v1/rag-retrieval/query/mmr` URL); otherwise defaults to
  `'similarity'`, unchanged from before this field existed - no
  auto-selection heuristic, since (as flagged when this was originally
  planned) there's no sourced signal for picking between the two from
  query text alone.

  **Dependency crisis, caused and then fully resolved in the same pass -
  documented in full because pip's resolver rejected three consecutive
  attempts before landing on a working set, not because it should have
  been hard:** installing `langchain-chroma`/`langchain-pinecone` with no
  version pins pulled `langchain-core` 0.3.86 → 1.6.3 and `openai`
  1.66.3 → 3.13.0 - both major-version jumps, and pip itself flagged the
  langchain-core one as incompatible with the pinned `langchain==0.3.20`
  (`requires langchain-core<1.0.0,>=0.3.41`). Reverted immediately, before
  writing any retriever code on top of it. Re-pinning
  `langchain-core<1.0.0` surfaced a second, three-way conflict:
  `llama-index-vector-stores-pinecone==0.9.0` needs `pinecone>=7,<10`;
  `langchain-pinecone` needs `pinecone>=6,<8` - `pinecone==7.3.0` is the
  only version satisfying both. Pinning that then surfaced a third:
  `langchain-pinecone==0.2.13` needs `langchain-openai>=0.3.11`, one
  patch above this project's pinned `0.3.9`. Letting pip resolve
  `langchain-openai` freely from there landed on `0.3.35`, which itself
  needs `openai>=2.x` - accepted only after live-verifying it doesn't
  break anything actually used: a real deep health check
  (`openai_client.py`'s `.models.list()`) and a real end-to-end RAG query
  (`embeddings.create()` + `chat.completions.create()`, the two calls
  actually used in production) both still worked correctly against
  `openai==2.54.0` before it was pinned. Final state: `langchain-core`
  stayed at `0.3.86` (unchanged), `pinecone` at `7.3.0` (was `9.1.0` after
  Phase 3, `10.0.0` originally), `openai` at `2.54.0` (was `1.66.3`),
  `langchain-openai` at `0.3.35` (was `0.3.9`) - see `requirements.txt`'s
  own comments for the exact forcing chain on each.

  **Two more real integration bugs found live, same category as Phase
  3's - a cross-library data-format mismatch, not guessable from docs:**

  1. **LangChain's Pinecone integration expects chunk text under a plain
     `"text"` metadata key, and silently *skips* (not just returns empty
     for) any result missing it** - worse than Phase 3's finding, where
     the old raw client at least returned empty text. LlamaIndex writes
     text inside a `"_node_content"` JSON blob instead (same root cause
     as Phase 3's finding, hit again here because LangChain's own
     similarity/MMR code paths do their own metadata handling, not
     `pinecone_client.py`'s query()). Fixed with
     `_TextBackfillPineconeIndex`, a thin wrapper around the real
     `pinecone.Index` that backfills a `"text"` key before LangChain ever
     sees a result - confirmed live: every LlamaIndex-written match was
     silently dropped without it, present and correct with it.

  2. **LangChain's MMR code path for Pinecone does an unguarded
     `metadata.pop("text")` (no fallback, unlike its similarity-search
     path) - a real live `KeyError: 500` on a mixed-format namespace.**
     Root cause, found by reading `langchain_pinecone`'s installed source
     directly, not guessed: `max_marginal_relevance_search_by_vector()`
     fetches `fetch_k` candidates (top_k × 3 by default - a wider net
     than plain similarity's top_k), and this project's real Pinecone
     namespace has vectors written *three* different ways across this
     rewrite's own history - the original hand-written indexer
     (`"document"` key), LlamaIndex (`"_node_content"`), and now this
     phase's own testing - so MMR's wider net was likelier to include an
     old-format vector with neither key. Fixed by extending the same
     wrapper to also check the legacy `"document"` key, and to guarantee
     `"text"` is always present afterward (empty string as the last
     resort) so LangChain's unguarded `pop()` never raises. Verified
     live: the exact request that 500'd before the fix returned a
     correct, diverse, grounded MMR answer after it.

  **Tests**: the old retriever tests used `FakeVectorStore` (a plain dict)
  against the raw-client version's `vector_store.query()` call directly -
  gone now, since `retriever.py` builds a real LangChain vector store
  requiring a real collection object, same reasoning Phase 3's indexer
  tests needed a real ephemeral Chroma collection. Rebuilt on the same
  pattern, plus a new `FakeEmbeddings` (registers exact text → vector
  pairs, no network call) so real cosine-similarity math runs against
  real, hand-placed vectors without ever calling OpenAI. Each test gets
  its own uuid-suffixed collection name (same fix Phase 3's tests needed
  for the same reason - ephemeral clients share collection storage by
  name within one process). All 10 original test cases adapted plus 2
  new ones (MMR returns `score: null`, an unknown `search_strategy`
  raises). 2 new route-level tests for the `/query/mmr` endpoint and the
  dynamic `search_strategy` field. Full suite green (88/88).

  **Verified live, real cost incurred, against both real backends**:
  plain similarity and MMR against real ChromaDB (MMR's sources visibly
  more diverse - one similarity source pulled 2 near-duplicate chunks
  from the same document, MMR's 3 sources spanned 3 different documents,
  for the identical query); plain similarity and MMR against real
  Pinecone (confirming both integration-bug fixes above); the dedicated
  `/query/mmr` endpoint and the dynamic `search_strategy` field, both
  ways of reaching the same code; an unknown `search_strategy` → `422`.
  Test documents deleted afterward.

  `README_TEST.md` (new cases 5.5-5.7), `requirements.txt` (every version
  change explained inline), and the Postman collection (4 new requests)
  updated to match.

  **Not done in this phase, carried forward as originally scoped**:
  score-threshold-gated fallback and multi-turn query reformulation -
  neither exists in this project today (the latter was incorrectly
  described as "already implemented, carrying forward" in an earlier
  status update to the user mid-phase; corrected once found not to be
  true - `pipeline.py`'s `decompose_query()` is a trivial `return [query]`
  stub, and `RagQueryRequest` has no `chat_history` field at all). Also
  not done: Tree/Keyword-Table/Hybrid indexing (documented as deferred in
  Phase 14.2's indexing entry above).

- [ ] **Phase 15 (planned, added 2026-09-13 on request) — Evaluation
  (workshop Module 5): retrieval metrics (Precision@K/Recall@K/F1) and
  generation metrics (groundedness/completeness via LLM-as-judge)
  against the now-rebuilt LangChain/LlamaIndex pipeline.** Distinct from
  the older Phase 8 evaluation item below (golden dataset done, harness
  planned, hand-written) - this is a new phase specifically for
  evaluating Phase 14's rebuilt pipeline, added directly on request after
  the user asked whether Module 5 had been included and was told it
  hadn't been (Phases 14.1/14.2 map to modules 2-4 plus the idempotency
  cleanup only). Not started.

- [x] **Phase 16 (Claude Code, 2026-09-14 on request) — Content-hash
  duplicate-upload detection, reinstated.** The first phase taken through
  the new SDD process end to end (`CLAUDE.md`'s SDD section): spec written
  via `/spec-new` below and reviewed before any code changed, exactly as
  planned.

  - **Spec:**
    - **Context:** Surfaced live - uploading the same PDF twice produced
      two separate documents (`b681dbdf...` and `b05ca4a7...`) instead of
      the second being flagged as a duplicate. Root cause: Phase 14.1
      (2026-09-13) removed the check, explicitly as a "complex optional"
      piece to drop for now, **"not a verdict on whether it's worth
      having."** `content_hash` is still computed and stored on every
      upload (`services/documents_service.py` line ~90); only the lookup
      against it was removed. `find_by_content_hash()` still exists,
      fully implemented, on `BaseMetadataClient`/`SqliteClient`/
      `PostgresClient`, DB-indexed. `DocumentUploadResult.status` and
      `DocumentUploadResponse.duplicate_count` still document `"duplicate"`
      as a real value. Nothing here is new design - it's restoring one
      deleted function call plus its tests. **Not the same mechanism as
      the still-deferred `Idempotency-Key` header cache** (Redis-backed
      re-implementation, no timeline) - that's HTTP-request replay
      protection; this is a persistent, DB-backed check against actual
      file content, unaffected by that limitation.
    - **Data/API contracts:** No model or client changes. `services/
      documents_service.py::save_upload()` gets exactly one new step,
      inserted between computing `content_hash` and the
      `supersedes_document_id` lookup (matching the original, pre-removal
      order precisely - see Open questions): call
      `get_db_gateway().metadata_store().find_by_content_hash(content_hash)`;
      if it returns a row, return `DocumentUploadResult(status="duplicate",
      document_id=<existing id>, message=<existing id/filename/version>,
      file_size_bytes=<existing>, document_version=<existing>)` instead of
      creating a new document.
    - **User-visible behavior:** Uploading byte-identical content -
      regardless of filename - returns `status: "duplicate"` pointing at
      the *existing* document's `document_id`/`document_version`, and
      `duplicate_count` on the response reflects it. No new row, file, or
      directory is created. Content that merely shares a filename but
      differs in bytes is unaffected - still `"uploaded"` as a new
      document, same as today.
    - **Failure modes:** None new - a duplicate is a per-file `200`
      result (`status: "duplicate"`), not an error, matching the existing
      partial-success batch-upload pattern.
    - **Retrieval quality criteria:** N/A - upload-time only, doesn't
      touch chunking/indexing/retrieval.
    - **Out of scope:**
      - The `Idempotency-Key` header cache / Redis re-implementation -
        separate mechanism, stays deferred.
      - Retroactively merging or cleaning up documents already
        duplicated during the window this check was off (including the
        `b681dbdf...`/`b05ca4a7...` pair from the report that prompted
        this) - this fix only prevents *new* duplicates; existing ones
        are a separate, explicit cleanup task if wanted.
      - Fuzzy/near-duplicate detection (embedding-similarity based, not
        exact hash) - a materially different feature, not this fix.
    - **Open questions:** The original implementation ran the duplicate
      check *before* validating `supersedes_document_id` - so if a
      caller uploads content that happens to match an existing document's
      hash while also passing `supersedes_document_id`, the result is
      `"duplicate"` and the supersede is silently skipped, not an error.
      Restoring that exact ordering as part of "same as before," not
      changing it - flagged here since it's a real interaction a caller
      could hit, not because it needs a decision before implementing.

  **Verified:** the exact reported scenario reproduced live against a real
  `TestClient` call (upload `JPMC Healthcare Benefits.pdf` twice, identical
  bytes) - first upload `status: "uploaded"`; second `status: "duplicate"`,
  `duplicate_count: 1`, pointing at the first upload's `document_id`, no
  second document created. Full test suite green (89/89 - was 88, minus the
  now-inverted `test_uploading_identical_content_twice_creates_two_separate_
  documents`, plus the two restored duplicate tests). Note: this fix only
  prevents *new* duplicates - the `b681dbdf...`/`b05ca4a7...` pair from the
  original bug report predates it and still exists as two documents; no
  retroactive cleanup was done (see Out of scope above).

- [x] **Phase 17 (Claude Code, 2026-09-14 on request) — Indexing write
  path standardized on LangChain's `index()`/`SQLRecordManager`, replacing
  LlamaIndex.** Chosen as "Option A" of three presented (full swap vs. a
  surgical hash-tracking-only adoption vs. concept-only) - the one that's
  actually "as per LangChain's documentation," not just LangChain-flavored.

  - **Spec:**
    - **Context:** User asked to standardize the document-update path on
      LangChain's own indexing API. Checked feasibility first:
      `langchain.indexes.index()` + `SQLRecordManager` are installed and
      real (`langchain==0.3.20`), and `retriever.py` already builds the
      exact `Chroma`/`PineconeVectorStore` LangChain objects `index()`
      needs - they're just not used for writing yet. **This reverses a
      deliberate Phase 14.2 decision** ("one library per pipeline stage" -
      LlamaIndex specifically for indexing, recorded in `CLAUDE.md`).
      Overturning a recorded decision needs its own recorded reason, not a
      silent swap - see the `docs/FAQ.md` entry this phase must add.
    - **Data/API contracts:** No external contract changes - confirmed.
      `IndexResponse` keeps the same shape; callers of `POST .../index` see
      no difference except the new real capability: **skip-if-unchanged**.
      Internally, `ai/doc_processing/indexing/vector_indexer.py::write_chunks()`
      was rewritten onto `langchain.indexes.index()` (`cleanup="incremental"`,
      `source_id_key="document_id"`), against a shared LangChain vector
      store builder moved to `common/clients/db_client/langchain_vector_store.py`
      (not left in `retriever.py` - importing it from there would have
      created a circular import once `vector_indexer.py` needed it too;
      `common/` is the right home since neither pipeline should depend on
      the other's module). `sqlalchemy` pinned explicitly in
      `requirements.txt`; the now-unused `llama-index-*` packages removed
      from it entirely (nothing in `src/` imports `llama_index` anymore -
      confirmed by grep before removing). **Two real gaps found only while
      implementing, not anticipated by the spec as written - both resolved,
      not glossed over:**
      1. **Chunk ids.** `index()` computes each chunk's id itself (a hash),
         it doesn't accept an arbitrary caller-supplied one - confirmed by
         reading the actual installed source
         (`langchain_core/indexing/api.py`), not assumed from docs. This
         project's delete/supersede logic depends on ids it can compute
         itself. Resolved with a custom `key_encoder` callable
         (`build_chunk_id()`: `document_id:chunk_index:content_hash`) -
         close enough to the old `document_id:chunk_index` scheme that
         delete/supersede logic barely changed, while still giving
         `index()` a real, content-derived signal to detect a change by.
         One consequence caught in testing: `update_metadata()` replaces a
         chunk's full metadata dict, so the supersede-flip step must keep
         passing `chunk_index` explicitly (parsed back out of the id) -
         an early version of this dropped it, silently wiping the field;
         caught by asserting on it directly, not just on the report shape.
      2. **Embeddings.** `index()` embeds internally via the vector store's
         own embedding function - it can't accept pre-computed embeddings.
         The old pipeline computed embeddings separately first
         (`embedding_generator.py`), which would have meant embedding
         every chunk *twice*, and silently breaking the documented
         `embedding_model` per-call override (the vector store's embedding
         function didn't know about it). Resolved: `get_vector_store()`
         now takes an `embedding_model` override directly;
         `pipeline.py`'s separate pre-embedding step was removed
         (`embedding_generator.py` itself is untouched, just no longer
         called from the main pipeline); `embedding_dimension` is measured
         with one cheap `embed_query()` call, not by re-embedding
         everything a second time.
      - `documents_service.py`'s delete path also had to change:
        `storage_chunk_ids()` (a workaround for a LlamaIndex-specific
        Pinecone id-prefixing quirk) no longer applies now that indexing
        doesn't go through LlamaIndex at all - deleting a document would
        have silently targeted the wrong ids on Pinecone otherwise.
        `storage_chunk_ids()` itself is now dead code, left in place, not
        deleted, since it's still referenced from `vector_indexer.py`'s
        module docstring history - worth a follow-up cleanup, not urgent.
      - **The cross-document `supersedes_document_id`/`is_current` flip
        stays this project's own logic**, confirmed unaffected in
        substance - `SQLRecordManager` has no concept of "a different
        document replaces this one," only "this source_id's own content
        changed." Live-tested (see Verified below): `chunk_index` and
        `is_current` both survive the flip correctly.
    - **User-visible behavior:** Confirmed live - re-indexing unchanged
      content reports `chunks_indexed: 0` (was previously always > 0 on
      any re-index). Changed content is re-indexed and the old chunk
      cleaned up. Stale chunks from a shrunk/changed document are deleted
      for real via `index()`'s own cleanup.
    - **Failure modes:** No new ones, confirmed - `write_chunks()` still
      returns the same `dict` shape `IndexResponse` expects.
    - **Retrieval quality criteria:** N/A - `retriever.py`'s search logic
      itself is unchanged; it now imports its vector-store builder from
      the new shared module instead of defining it locally, same behavior.
      Existing vectors written by the old LlamaIndex path remain fully
      queryable - confirmed no migration was needed.
    - **Out of scope, confirmed:** chunking (`text_chunker.py`) untouched;
      no migration/backfill of already-indexed documents; no change to the
      Phase 16 duplicate-upload check.
    - **Open questions:** the flagged count-reporting change
      (`chunks_indexed: 0` on a genuinely unchanged re-index) is real and
      confirmed live - no existing test asserted the old, wrong-by-design
      behavior, so nothing needed correcting there.
  **Verified:** full test suite green (90/90 - two tests rewritten for the
  new skip/cleanup counts, `test_retriever.py` updated for the moved
  vector-store builder, `FakeEmbeddings` moved to `conftest.py` as a
  shared fake so no test needs a real OpenAI call). Live, end-to-end
  through the real API: upload → first index (48 chunks) → second index of
  *identical* content (`chunks_indexed: 0`, confirmed real skip-if-unchanged) →
  a real grounded query with 5 sources → delete (48 chunks removed, confirming
  the new ids delete correctly) → 404 after. Supersede-flip tested directly
  against a real ChromaDB collection, confirming `chunk_index`/`is_current`
  both survive. **Pinecone path implemented identically but not verified
  live against a real Pinecone account in this session** - same category of
  caveat this project already uses elsewhere (e.g. Postgres, "healthy
  locally, not the active store yet"). One unrelated bug found and fixed
  live during this work: `.claude/scripts/spec_gate.py`'s phase-detection
  regex silently stopped scanning after Phase 4.5 (this file's phase
  content spans two separate `##` headings, not one) - caught because the
  gate itself blocked this phase's first real edit; fixed, verified both
  branches (allow/deny) still correct, not just the one that was broken.

- [x] **Phase 18 (done, 2026-09-14) — Chunking-strategy
  auto-selection: log the rationale, not just the result.** "Option 1" of
  two presented (deterministic + richer logging vs. an LLM-based content
  reviewer) - chosen after checking LangChain's and LlamaIndex's own
  documentation, neither of which recommends or documents an automatic,
  content-inspecting strategy-picker; both frame splitter choice as a
  stable, structural, upfront decision. That's what `decide_chunking_
  strategy()` already does - this phase makes it explain itself, it
  doesn't redesign it.

  - **Spec:**
    - **Context:** User asked for the chunking-strategy auto-selection to
      review document content and log its reasoning. `decide_chunking_
      strategy()` (`ai/doc_processing/chunking/text_chunker.py`) already
      makes this decision on every upload where `chunking_strategy` isn't
      given explicitly - it just doesn't say *why* beyond `logger.info(
      "chunking: auto-selected strategy=%s", strategy)`.
    - **Data/API contracts:** None. `decide_chunking_strategy()` keeps its
      exact signature and return type (`str`) - no caller (`chunk_text()`,
      `pipeline.py`, `IndexResponse`) changes. This is a logging-only
      change, not a new field surfaced to API callers - the user asked to
      *log* the rationale, not return it.
    - **User-visible behavior:** None from the API's point of view.
      Server-side log output for an auto-selected strategy changes from
      "auto-selected strategy=markdown" to something that names the actual
      evidence, e.g. "3 markdown heading line(s) found -> 'markdown'" /
      "1847 characters, at or under the 2000-character whole-document
      threshold -> 'none'".
    - **Failure modes:** None new - this function has never raised; it
      isn't gaining a code path that could.
    - **Retrieval quality criteria:** N/A - decision logic itself is
      unchanged, only its logging.
    - **Out of scope:**
      - No new detection signals (e.g., table density, code-block
        detection) and no new thresholds - this file's existing
        thresholds are already "measured, not guessed" (see
        `WHOLE_DOCUMENT_MAX_LENGTH`'s own history); inventing new ones
        without the same grounding would repeat exactly the mistake this
        codebase has avoided elsewhere. Logging the *existing* rules'
        evidence, not adding rules, is the whole scope.
      - No separate "pre-processing" module/file - the enhanced function
        stays in `text_chunker.py`. A new file for ~15 extra lines of
        logging would be the premature abstraction this project's own
        conventions argue against; revisit only if the logic actually
        grows past this.
      - `"semantic"` stays excluded from auto-selection, unchanged - its
        existing rationale (accuracy-criticality isn't detectable from
        text alone) still holds and this phase doesn't relitigate it.
    - **Open questions:** none.
  **Verified:** full test suite green (93/93, unchanged - confirms the
  decision *rules* genuinely didn't change, only their logging). Live-ran
  all four branches directly: markdown (`2 markdown heading line(s) found`),
  html (`HTML heading tag(s) ['<h2'] found`), none
  (`30 character(s), at or under the 1000-character... threshold`), and
  recursive (`3199 character(s), ... over the 1000-character threshold`) -
  each logs the real evidence, not just the chosen name.

- [x] **Phase 19 (done, 2026-09-14) — Chunk-level
  metadata expansion for filtering: `doc_type`, `department`, and a new
  `doc_classification` field.** Foundation for Phase 20 (Self-Query needs
  real filterable metadata to parse queries into) - not useful on its own
  beyond enabling manual `filter=` queries by these fields.
  **Depends on Phase 17 landing first** - this touches the exact write
  path Phase 17 rewrites; building it against today's LlamaIndex-based
  `write_chunks()` first would mean redoing it once Phase 17 replaces
  that function. `timestamp` deliberately excluded from this phase, per
  explicit request.

  - **Spec:**
    - **Context:** Today, `owner`/`department`/`doc_type`/`purpose` are
      extracted by `document_metadata_extractor.py` (LLM, best-effort,
      first-3000-characters-only) but only ever written to the **SQL**
      `documents` row - never to vector-store chunk metadata, which today
      only carries `chunk_index`/`is_current`/`indexed_at`. That means
      none of them can be used in `retriever.py`'s `filter=` kwarg, the
      same mechanism `is_current` already uses. `owner` and `purpose` are
      deliberately excluded from this expansion (see Out of scope) - not
      an oversight.
    - **Data/API contracts:**
      - New SQL column `doc_classification TEXT`, same `ALTER TABLE`
        pattern as the existing `owner`/`department`/`doc_type`/`purpose`
        columns, in both `sqlite_client.py` and `postgres_client.py`.
      - `document_metadata_extractor.py`'s `EXTRACTION_QUESTION` prompt
        and `EMPTY_RESULT` gain a fifth field, `doc_classification` - free
        text, best-effort, same shape as `doc_type` (not a fixed enum;
        real documents vary too much to hardcode a closed list - e.g.
        "401k", "health benefits", "leave policy", whatever the document
        itself indicates).
      - `DocumentRecord` (`models/documents.py`) gains a `doc_classification: str | None` field, matching `doc_type`'s existing shape exactly.
      - Chunk metadata gains `doc_type`, `department`, `doc_classification`
        alongside today's `chunk_index`/`is_current`/`indexed_at`.
    - **User-visible behavior:** `GET /documents/{id}` now reports
      `doc_classification` like it already reports `doc_type`. No new
      endpoint or query-facing behavior yet - Phase 20 is what actually
      lets a query use these filters.
    - **Failure modes:** None new - extraction is already best-effort and
      already never blocks indexing; a failed extraction just leaves
      `doc_type`/`department`/`doc_classification` null on that document's
      chunks, same as `owner`/`purpose` already can be today.
    - **Retrieval quality criteria:** N/A directly (Phase 20 covers actual
      filtered retrieval) - but worth stating the mechanism precisely
      since it's easy to get backwards: on a **re-index** of a document
      that's already been through first-index extraction,
      `doc_type`/`department`/`doc_classification` are already known (sitting
      in the SQL row `write_chunks()` already fetches as `existing_document`)
      and go straight into the chunk metadata built at write time - no
      follow-up write needed. Only a document's **first-ever** index needs
      a second, follow-up `vector_store.update_metadata()` call once
      extraction finishes after indexing (same shape as the existing
      supersede-flip pattern, not a new one) - because extraction runs
      *after* chunks are written for a first index, so those three fields
      genuinely aren't known yet at write time.
    - **Out of scope:**
      - `timestamp` - explicitly excluded per request.
      - `owner`, `purpose` - not filter candidates (`owner` is
        audit/display, not something a query implies; `purpose` is a free
        sentence, not a categorical value a filter can match on). Not
        propagated to chunk metadata.
      - Backfilling chunk metadata for already-indexed documents - only
        applies going forward; an old document gets these fields on its
        next re-index, not retroactively.
      - Any actual use of these fields in retrieval - that's Phase 20.
    - **Open questions:** none - the exact code this touches (which
      function builds chunk metadata, in what shape) depends on whether
      Phase 17 has landed by the time this is implemented; the fields and
      behavior above hold either way.
  **Verified:** full test suite green (97/97 - one existing extraction test
  updated for the new field, five new tests added covering both mechanisms:
  a first index leaves `doc_type`/`department`/`doc_classification` out of
  the initial chunk metadata entirely rather than null; the follow-up
  `apply_extracted_chunk_metadata()` patch preserves `chunk_index`/
  `is_current`/`indexed_at` while adding the three new fields, same
  REPLACE-semantics lesson as the Phase 17 supersede-flip; a re-index pulls
  the fields straight from `existing_document`; and either path omits a
  field entirely when extraction couldn't determine it, since Pinecone's
  `update()` rejects a literal `None` value outright while Chroma silently
  drops it - confirmed by direct test against a real ephemeral Chroma
  client). Live-verified end to end against the real OpenAI extraction
  call, a real Chroma collection, and the real SQLite metadata store
  (`resources/kb_docs/JPMC Guild Tuition Assistance.pdf`): first index -
  chunk metadata came back
  `{'doc_type': 'benefits', 'department': None, 'doc_classification':
  'Guild Education benefit program', 'is_current': True, 'chunk_index': 0}`
  (an absent `department` key confirmed - the extractor genuinely found
  none for this document, and that's a missing key, not a stored null);
  re-index (after manually setting the SQL row's `doc_classification` to a
  sentinel value, to prove the value is read fresh from SQL at write time
  rather than reused from the first index) - the new chunk immediately
  carried the sentinel value, no follow-up call involved.

- [x] **Phase 20 (done, 2026-09-14) — MultiQueryRetriever
  and Self-Query Retriever.** **Depends on Phase 19** - Self-Query has
  nothing to parse a filter into without Phase 19's chunk metadata.
  Chosen after checking real-world LangChain guidance for RAG retrieval
  optimization (see the chat discussion this spec follows from).

  - **Spec:**
    - **Context:** User wants two of LangChain's documented retrieval
      techniques: `MultiQueryRetriever` (rewrites one question into several
      variations, searches with each, merges results - catches phrasing a
      single query misses) and Self-Query Retriever (an LLM parses the
      question itself into a structured metadata filter, e.g. "what's my
      401k vesting schedule" -> `doc_classification="401k"`).
    - **Data/API contracts:**
      - Both are **layers on top of** the existing similarity/MMR choice,
        not a third alternative to it - `RagQueryRequest` gains two new
        optional, explicit, default-`False` fields: `use_multi_query: bool`
        and `use_self_query: bool`. Neither changes the meaning of
        `search_strategy` - they wrap whichever base retriever
        (similarity or MMR) `search_strategy` already selects. Explicit
        opt-in on both, not inferred from the query text - matches this
        project's existing "no magic, override is always explicit" pattern
        (`vector_db`, `chunking_strategy`, etc. all work the same way).
      - `RagQueryResponse` gains an optional field surfacing what
        Self-Query actually parsed out (e.g. `applied_filter: dict | None`)
        - without this, a wrong or surprising filter would be undebuggable
        from the API response alone.
      - Self-Query needs an `AttributeInfo` list (LangChain's own schema
        for "what fields exist, what they mean") built from Phase 19's
        three filterable fields (`doc_type`, `department`,
        `doc_classification`) - `is_current` is deliberately NOT exposed
        to self-query's schema; it's an internal/system field a user
        question would never naturally reference, and it must stay under
        this project's own control (see Phase 16's careful handling),
        not something an LLM-parsed filter should be able to override.
    - **User-visible behavior:** With both flags off (the default), query
      behavior is byte-for-byte unchanged from today. With
      `use_multi_query: true`, more candidate chunks get considered before
      the same top_k is returned. With `use_self_query: true`, the query
      is filtered by whatever `doc_type`/`department`/`doc_classification`
      the model parses out of the question - `applied_filter` in the
      response shows exactly what was applied.
    - **Failure modes:** Self-Query's own LLM parse can fail or return no
      filter - falls back to an unfiltered search rather than erroring,
      same "best-effort, never block the user's answer" philosophy as
      `document_metadata_extractor.py`.
    - **Retrieval quality criteria:** Golden dataset
      (`resources/golden_dataset/golden_dataset.json`) should be re-run
      with both flags on and off to confirm neither regresses the
      default-off path and that self-query's parsed filters are actually
      correct on questions that name a specific plan/department.
    - **Out of scope:** `ContextualCompressionRetriever`/reranking,
      Parent-Document Retriever, `EnsembleRetriever`/hybrid BM25 search -
      all discussed as options, none requested yet.
    - **Open questions:** none.
  **Addendum, found during implementation (2026-09-14) - same "flag real
  gaps found mid-implementation" discipline as Phase 17's two gaps:**
    - **Real dependency deadlock, confirmed by trying it live:** LangChain's
      own per-provider chat packages can't be installed here at all.
      `langchain-anthropic`'s newest 0.3.x release (the last one compatible
      with this project's `langchain-core==0.3.86`, itself required by
      `langchain`/`langchain-openai`/`langchain-pinecone`/`langchain-chroma`)
      hard-requires `anthropic<1.0.0`, but this project's own
      `anthropic_client.py` needs `anthropic==1.2.0`. Every newer
      `langchain-anthropic` release needs `langchain-core>=1.6`, which
      breaks the rest of the pinned stack instead. No version satisfies
      both - confirmed by actually installing each combination, not just
      reading changelogs. Resolution: `common/clients/llm_client/
      langchain_chat_model.py` (new) - a small `BaseChatModel` subclass
      (`GatewayChatModel`) wrapping this project's own multi-provider
      `ask()` clients via `client_gateway.py`. Zero new dependencies, and
      it's the same gateway/enum pattern CLAUDE.md already documents
      instead of bypassing it for a per-provider LangChain package.
    - **`RagQueryRequest` had no provider selector at all before this** -
      `model_name` only ever overrides `OpenAIChatClient`'s model in
      `response_generator.py::generate_answer()`, which stays OpenAI-only,
      unchanged (out of scope for this phase - flagging it, not fixing
      it). New field `llm_provider: LlmProvider | None` (defaults to
      `openai`) picks which provider backs `GatewayChatModel` for
      MultiQueryRetriever's rewriting / Self-Query's filter-parsing only -
      independent of the final answer's model.
    - **`retrieve_chunks()`'s return type changes** from `list[dict]` to
      `tuple[list[dict], dict | None]` (chunks, applied_filter) to carry
      `applied_filter` up to `answer_query()`/`RagQueryResponse` - ripples
      through `ai/rag_pipeline/pipeline.py` and its own tests.
    - **is_current must never be overridable by a parsed filter** (the
      spec's own stated rule) - a plain dict merge of Self-Query's parsed
      filter with `CURRENT_CHUNKS_ONLY` would let a same-shaped key
      silently replace it, so they're explicitly AND-ed together
      (`{"$and": [CURRENT_CHUNKS_ONLY, parsed_filter]}`) instead of merged.
    - **Both flags together:** not mutually exclusive - if both are true,
      Self-Query's filter is parsed once from the *original* question
      (filtering intent shouldn't come from a MultiQuery paraphrase), then
      MultiQueryRetriever wraps a base retriever already constructed with
      that combined filter.
  **Verified:** full test suite green (106/106 - 5 new retriever-level
  tests using a fake `BaseChatModel` double, so none of them spend real API
  cost: `_combine_with_current_only()`'s bare-vs-AND-combined cases,
  `search_multi_query()` merging/deduping across LLM-rewritten sub-queries,
  `_parse_self_query_filter()` both parsing a real filter and returning
  `None` when the model finds nothing to filter on, and the core
  correctness case the spec calls out explicitly - a superseded chunk that
  *also* matches the parsed filter is still excluded, `is_current` proven
  un-overridable; plus 3 new route-level tests for `use_multi_query`/
  `use_self_query`/`llm_provider`/`applied_filter`). Live-verified against
  real OpenAI + a real indexed document
  (`resources/kb_docs/JPMC Empower 401(k) Savings Plan.pdf`) through the
  real `/v1/rag-retrieval/query` endpoint: `use_multi_query=true` alone
  retrieved 7 real chunks and generated a grounded answer; `use_self_query`
  alone correctly parsed `{"doc_type": {"$eq": "benefits"}}` and matched 5
  real chunks when queried in isolation; both flags together ran without
  error, self-query's filter parsed once from the original question, then
  fed into the multi-query-wrapped base retriever, exactly as spec'd.
  **One real, honest limitation found during this live verification, not
  glossed over:** `doc_classification` is deliberately free text (Phase
  19's own design - "not a fixed enum, real documents vary too much"), so
  Self-Query's `$eq` filter only matches when its LLM's guessed value
  happens to exactly match what extraction actually stored - e.g. the LLM
  reliably parses `doc_classification="401k"` from a "what's my 401k
  vesting schedule" question (matching `METADATA_FIELD_INFO`'s own written
  example), but this document's real extracted value is `"401(k) Savings
  Plan"`, an exact-string mismatch that correctly-but-uselessly returns zero
  chunks. `doc_type` (semi-controlled - extraction picks from a short fixed
  list) does not have this problem, confirmed by isolating it: filtering on
  `doc_type=benefits` alone matched real chunks every time. This is a real
  design tension between Phase 19's free-text field and Self-Query's
  exact-match semantics, not a Phase 20 bug - flagging it as a follow-up
  item (e.g. a `contain`/fuzzy comparator, or re-scoping
  `doc_classification` toward a smaller controlled set) rather than fixing
  it now, since it wasn't part of this phase's spec.

- [x] **Phase 21 (Claude Code, 2026-09-14 on request) — Remove the
  duplicate per-strategy endpoints; one endpoint each for ingestion and
  retrieval.** Implemented before Phases 18-20, as recommended - not a
  hard technical dependency, but Phase 20 adds new fields to
  `RagQueryRequest`, and doing that against a single query endpoint
  instead of two is simpler and avoids touching the soon-to-be-removed
  `/query/mmr` at all.

  - **Spec:**
    - **Context:** This API currently has two endpoints for the same
      operation, twice: `POST /documents/{id}/index` (dynamic,
      `chunking_strategy` as an optional body field) and `POST
      /documents/{id}/index/{chunking_strategy}` (one URL per strategy,
      fixed from the path); `POST /query` (dynamic, `search_strategy` as
      an optional body field) and `POST /query/mmr` (fixed to MMR). Each
      pair does the identical thing two different ways. Consolidate to one
      endpoint per resource, strategy selection always via the request
      body - matches how every other override on these endpoints already
      works (`vector_db`, `embedding_model`, `chunk_size`, `top_k`, ...).
    - **Data/API contracts:**
      - **Removed:** `POST /documents/{id}/index/{chunking_strategy}`
        (`routes_documents.py::index_document_with_strategy()`) and `POST
        /query/mmr` (`routes_query.py::query_mmr()`). Both routers'
        shared helpers (`_index_document()`, `_answer_query()`) stay -
        still used by the one remaining route each.
      - `IndexRequest.chunking_strategy` and `RagQueryRequest.search_strategy`
        become real `StrEnum`s (`ChunkingStrategy`, `SearchStrategy` in
        `common/enums.py`), matching the `VectorDB`/`MetadataStore`/
        `LlmProvider` pattern already established. Reason this matters now
        and didn't before: removing the URL-based endpoints removes the
        404-at-the-path-level validation they gave "for free" - without
        converting to an enum, an unknown strategy would only be caught
        deeper in the pipeline (a `ValueError` a few calls in), not at the
        API boundary. `CHUNKING_STRATEGIES`/`SEARCH_STRATEGIES` (the
        dispatch dicts in `text_chunker.py`/`retriever.py`) stay exactly
        as they are - dict keys and enum values must simply agree, not be
        merged into one structure.
      - `README.md`'s `.../index/recursive` example and the Postman
        collection's three `/index/{strategy}` requests + one `/query/mmr`
        request are removed; the surviving dynamic-endpoint examples
        already demonstrate `chunking_strategy`/`search_strategy` as body
        fields.
    - **User-visible behavior:** `POST /documents/{id}/index/recursive`
      and `POST /query/mmr` return `404` (unmatched route) after this
      phase - a real, intentional breaking change, not an oversight.
      `POST /documents/{id}/index` with `{"chunking_strategy":
      "recursive"}` and `POST /query` with `{"search_strategy": "mmr"}`
      are the replacements - already supported today, unchanged.
    - **Failure modes:** An unknown `chunking_strategy`/`search_strategy`
      value now returns `422` (Pydantic enum validation) instead of the
      old dynamic endpoint's `ValueError`-derived `422` or the removed
      URL endpoint's `404` - one consistent shape across both, at the API
      boundary instead of a few calls into the pipeline.
    - **Retrieval quality criteria:** N/A - no chunking/retrieval logic
      changes, only which URLs reach it and how the value is validated.
    - **Out of scope:**
      - No change to `POST /documents` (upload), `GET`/`DELETE`
        `/documents[/{id}]`, or any query field other than
        `search_strategy`.
      - Not bundling Phase 19/20's new fields into this phase - this is
        endpoint surface cleanup only.
    - **Open questions:** none.
  **Verified:** full test suite green (93/93 - one obsolete test removed,
  three added covering the new 404s and the enum-driven 422s). Live-checked
  directly: `.../index/recursive` and `POST /query/mmr` both now `404`;
  `{"chunking_strategy": "not-a-real-strategy"}` and an unknown
  `search_strategy` both `422`, naming the valid options.

  Doing this surfaced staleness well beyond this phase's own scope, fixed
  alongside it rather than left for later:
  - `CLAUDE.md`'s architecture section still said LlamaIndex writes vectors
    (Phase 17 changed that) - fixed.
  - `README_TEST.md` - a *living* reference ("every endpoint this project
    **currently has**"), not a historical one - had drifted across this
    entire session, not just this phase: the removed `deep=true` health
    toggle, the *reinstated* (Phase 16) duplicate-upload detection still
    described as removed, and `IndexRequest.vector_db`'s enum conversion
    (turn 1 of this session) never reflected in its "expect 500" edge
    case. All corrected and re-verified live against the real server, not
    just reworded.
  - `postman/hrb_chatbot.postman_collection.json` - the two removed
    endpoints' requests deleted; their edge cases repurposed (not
    dropped) to test the same intent through the surviving path.

- [x] **Phase 22 (done, 2026-09-15) — Comment-length
  cleanup across `src/hrb_chatbot/`, plus a codified 2-line rule.** Comment
  length drifted longer phase over phase this session (module docstrings up
  to 18 lines, inline blocks up to 9) - this phase both fixes the existing
  drift and writes the limit down so it doesn't recur.

  - **Spec:**
    - **Context:** `docs/CODING-STANDARDS.md` already said "a line or two,
      not a paragraph" but without a hard number or a stated exception -
      an AST/regex scan of `src/hrb_chatbot/` found 94 violations (a
      comment/docstring over 2 content lines) across 36 files.
    - **Data/API contracts:** None - comments and docstrings only, zero
      behavior change. `docs/CODING-STANDARDS.md` and
      `.claude/skills/coding-standards/SKILL.md` gain an explicit two-line
      hard limit, third line allowed only at a genuinely critical spot.
    - **User-visible behavior:** None - same reason.
    - **Failure modes:** None new.
    - **Out of scope:** `tests/` (a different, already-consistent short-
      "why" style; not what drifted) and non-Python docs (`docs/*.md`,
      `CLAUDE.md`) - those are reference material, not the "comment" this
      request means.
    - **Open questions:** none.
  **Verified:** all 36 flagged files edited by hand (not scripted) across
  every layer (`common/clients/`, `ai/doc_processing/`, `ai/rag_pipeline/`,
  `api/`, `services/`, `main.py`) - 94 violations (over 2 content lines) down
  to 0 over the 3-line hard ceiling, ~48 legitimate 3-line exceptions kept
  for genuinely critical spots (REPLACE-semantics gotchas, the is_current
  override-safety boundary, the Pinecone/langchain-core dependency
  deadlock), confirmed by an AST/regex re-scan after every batch. One
  long-standing dead docstring reference fixed along the way
  (`routes_documents.py` pointed at a module docstring that didn't exist)
  and one stale claim fixed (`rag_service.py::answer_query()` still said
  "Raises NotImplementedError until Phase 6 exists", untrue since Phase 6
  shipped long ago). One long docstring's real content relocated rather
  than deleted - `langchain_vector_store.py`'s `_TextBackfillPineconeIndex`
  moved to `docs/FAQ.md`'s new entry 8, source trimmed to a 3-line pointer.
  Full test suite green (106/106) after every batch, plus a live `/ping`
  smoke test at the end. `docs/CODING-STANDARDS.md` and
  `.claude/skills/coding-standards/SKILL.md` both codify the 2-line rule
  (3 sparingly) going forward, so this doesn't drift again unnoticed.
  **Flagged, not fixed (outside this phase's scope):** `PineconeClient.
  query()`/`.upsert()` and `ChromaClient`'s equivalents appear to be dead
  code in the current pipeline - indexing/retrieval both go through
  LangChain's own vector store objects now (`langchain_vector_store.py`),
  not these raw methods directly; confirmed by grepping for other callers
  and finding none. Worth a real look in a future phase, not this one.

- [x] **Phase 23 (done, 2026-09-15) — FastAPI gateway
  layer: role-based access in front of RAG ingestion + retrieval, OAuth
  placeholder.** Follows a conversation weighing a real API Gateway
  (AWS API Gateway/Kong) against in-app FastAPI dependencies - the user
  confirmed in-app. Sequenced ahead of Phase 15 (Evaluation) and today's
  planned ReAct agent work, kept intentionally tight so it doesn't block either.

  - **Spec:**
    - **Context:** Today there is zero authentication or authorization -
      every endpoint is reachable by anyone who can reach the URL. The user
      wants: only an `HR_SUPPORT` role can reach the ingestion API (upload/
      list/get/delete/index a document); `EMPLOYEE`, `MANAGER`, and
      `HR_SUPPORT` can all reach retrieval (query), uniformly - no
      per-document visibility differences yet, deliberately deferred. Real
      OAuth is explicitly deferred too - this phase builds the seam
      (dependency-injection point + role enum + 401/403 semantics) a real
      OAuth integration will slot into later, not real authentication now.
    - **Data/API contracts:**
      - New `Role` `StrEnum` in `common/enums.py`: `EMPLOYEE`, `MANAGER`,
        `HR_SUPPORT` - matching the existing `VectorDB`/`LlmProvider` pattern.
      - New `api/gateway/` package: `current_user.py` (a `CurrentUser`
        dataclass - `employee_id`, `full_name`, `role` - and a
        `get_current_user(request)` FastAPI dependency reading three
        request headers) and `rbac.py` (`require_role(*allowed_roles)`, a
        dependency factory raising 403 when the resolved role isn't in the
        allowed set).
      - **Identity source, explicitly not real security:**
        `X-Employee-Id`/`X-Full-Name`/`X-Role` request headers, read as-is,
        no signature/verification. This is a deliberate, honestly-labeled
        placeholder - trivially spoofable by design, not a security
        control. All three are required (401 if any is missing, or if
        `X-Role` doesn't match a real `Role` value) - fail closed, and
        modeling what a real verified token's claims would guarantee,
        rather than defaulting silently.
      - `main.py` wires `Depends(require_role(...))` at
        `app.include_router(...)` level for both routers - a router-level
        gate, not injected into individual route handlers. Nothing in
        `routes_documents.py`/`routes_query.py` changes.
      - `common/error_codes.py` gains `UNAUTHENTICATED` (401) and
        `FORBIDDEN` (403); `main.py`'s existing `HTTPException` handler
        (already maps 429 -> `RATE_LIMITED`) gains these two mappings -
        explicit codes, not a defaulted `INTERNAL_ERROR`, matching
        `CODING-STANDARDS.md`'s existing error-code rule.
      - New empty placeholder: `common/clients/auth_client/oauth_client.py`
        (0 bytes, matching the existing `llm_client`/`db_client`/
        `web_client` sibling pattern) - real OAuth lands here later; only
        `get_current_user()`'s internals will need to change when it does,
        nothing calling it.
    - **User-visible behavior:** Every ingestion request now needs all
      three headers with `X-Role: hr_support`, or it's a 401/403. Every
      retrieval request needs all three headers with `X-Role` one of
      `employee`/`manager`/`hr_support`. `GET /ping` and `GET /health`
      stay open (operational endpoints, not business data).
    - **Failure modes:** Missing any identity header -> 401 naming which
      header(s). Unknown `X-Role` value -> 401 naming the valid options.
      Valid identity, wrong role for this router -> 403 naming the
      required role(s). Existing rate limiting (`enforce_rate_limit`)
      is unchanged and stacks with this - both dependencies apply.
    - **Retrieval quality criteria:** N/A - no retrieval-logic change.
    - **Out of scope:** Real OAuth/JWT/API-key verification (placeholder
      only, see above). Persisting `employee_id` onto `DocumentRecord` for
      upload audit trail (a natural follow-up, not required to gate
      access - flagged in `docs/BACKLOG.md`, not built here). Per-document
      visibility by role (deferred per the user's own instruction).
      Rate-limiting by identity instead of IP (still IP-keyed; noted as a
      future enhancement now that identity exists).
    - **Open questions:** none - reviewed conversationally over several
      turns before this spec was written, not a first draft.
  **Verified:** full test suite green (113/113 - 4 new gateway tests: no
  headers -> 401 naming the missing ones, unknown `X-Role` value -> 401,
  `employee`/`manager` attempting ingestion -> 403 naming the required
  role, all three roles accepted for retrieval; plus 2 existing
  `main.py::http_exception_handler` unit tests updated for the new
  explicit 401/403 code mappings). Live-verified end to end: `GET /ping`
  needs no headers (`200`); `GET /v1/rag-ingestion/documents` with no
  headers is `401` `UNAUTHENTICATED` naming all three missing headers;
  same call as `employee` is `403` `FORBIDDEN` naming `hr_support` as the
  required role; as `hr_support` it's `200` and actually lists real
  documents from the real SQLite store; `POST /v1/rag-retrieval/query` as
  `manager` reaches the real pipeline (ran retrieval + generation for
  real, not mocked). Existing test suite's two `TestClient` instances
  (`test_routes_documents.py`, `test_routes_query.py`) updated with
  default headers at the client level (one line each), not per call - no
  existing test's own behavior changed. `README_TEST.md` gained an
  upfront gateway-headers note plus a new, live-verified 1.7 case; the
  Postman collection's `RAG Ingestion`/`RAG Retrieval` folders gained a
  pre-request script injecting the placeholder headers automatically, so
  every existing request in both folders keeps working without editing
  each one by hand. `CLAUDE.md`'s request-flow section and
  `docs/BACKLOG.md` (real-OAuth, uploader-identity-persistence,
  identity-keyed rate limiting, per-document visibility - all explicitly
  out of scope here) updated to match.

- [x] **Phase 24 (done, 2026-09-15) — Fix:
  `validation_exception_handler` crashes on a malformed (non-JSON) body
  instead of returning a clean 422.** Found live while answering a user
  question about re-indexing (a multipart/form-data body sent to
  `POST /documents/{id}/index`, which expects JSON) - reproduced directly,
  root-caused, not guessed at.

  - **Spec:**
    - **Context:** When a request body fails to parse as JSON at all (not
      a field-level validation failure - the whole body is unparseable,
      e.g. a file sent where JSON was expected), Pydantic's
      `RequestValidationError.errors()` includes the raw request body
      bytes in its `"input"` field. `main.py`'s
      `validation_exception_handler` passes that straight to
      `jsonable_encoder()`, whose default `bytes` handling calls
      `.decode()` with no error handling - raising `UnicodeDecodeError`
      whenever those raw bytes aren't valid UTF-8 (any real binary file,
      e.g. a PDF). That crash happens *inside the exception handler
      itself* - Starlette has no fallback for an exception raised while
      already handling another exception, so it becomes a genuinely
      unhandled crash (a raw traceback in the console, no JSON response
      reaches the client) instead of the clean 422 every other malformed
      request gets.
    - **Data/API contracts:** `validation_exception_handler` gains
      `custom_encoder={bytes: lambda value: value.decode("utf-8",
      errors="replace")}` on its `jsonable_encoder()` call - malformed
      UTF-8 in the echoed-back `"input"` is replaced (`�`), never
      raised on. No response-shape change for every existing (already
      passing) validation-error case - `details` still carries the same
      Pydantic error list, just safe for binary edge cases too now.
    - **User-visible behavior:** A non-JSON body to any JSON endpoint now
      reliably gets a `422` with `code: "VALIDATION_ERROR"`, same as any
      other malformed request - never a raw crash.
    - **Failure modes:** None new - this closes a failure mode, doesn't add one.
    - **Out of scope:** Making the gateway or any route accept
      multipart/form-data on JSON-only endpoints - the fix is that a
      *rejection* of the wrong body shape is now clean, not that the
      wrong shape becomes accepted.
    - **Open questions:** none - root-caused via direct reproduction
      before this spec was written, not a guess.
  **Verified:** root-caused by direct reproduction (not guessed at) - a
  real multipart/form-data PDF body posted to `POST /documents/{id}/index`
  reproduced the exact `UnicodeDecodeError` class the user hit
  (`'utf-8' codec can't decode byte 0xd3'`). Confirmed the crash happens
  *inside* `validation_exception_handler` itself via
  `fastapi.encoders.ENCODERS_BY_TYPE[bytes]`'s default `lambda o:
  o.decode()`. Fixed with a `custom_encoder` on the `jsonable_encoder()`
  call; re-ran the exact failing request afterward - clean `422`,
  `code: "VALIDATION_ERROR"`, no crash. New regression test
  (`test_a_multipart_body_on_a_json_endpoint_is_a_clean_422_not_a_crash`)
  added and confirmed it actually catches the regression - failed with
  the exact same traceback when run against the pre-fix code (`git
  stash`), passed after. Full suite green (114/114).

- [x] **Phase 25 (done, 2026-09-15) — Reindex by
  filename, not just `document_id`.** Follows from a conversation about
  LangChain's own indexing model (`source_id_key` - one stable id per
  document, not resolved from a category/name-that-may-collide) - the
  conclusion was to keep `document_id` as that stable id, but let the
  caller reindex by filename too, since that's what they typically
  already know without a separate lookup.

  - **Spec:**
    - **Context:** `POST /documents/{document_id}/index` currently only
      accepts a real `document_id` in the URL - a caller who knows a
      document by name (not its system-generated id) has to `GET
      /documents` and search first. Filenames aren't unique in this
      system by design (Phase 16 - same name, different content, is a
      new document), so a name-based lookup can be ambiguous; a
      classification/type is a category shared by many documents, not a
      usable identifier at all (not proposed here for that reason).
    - **Data/API contracts:**
      - `POST /documents/{identifier}/index` - the path param is renamed
        `document_id` -> `identifier` in code (URL shape unchanged).
        Resolution: try `identifier` as a real `document_id` first
        (existing behavior, unchanged, ignores `is_current` - explicit id
        always wins regardless of supersede status). If no such id
        exists, treat it as a filename and match against **current**
        (`is_current=true`) documents only.
      - Zero matches (neither an id nor a current filename) -> `404`
        `DOCUMENT_NOT_FOUND`, same as today.
      - Exactly one filename match -> reindex it, identical to passing
        its `document_id` directly.
      - More than one filename match -> new `409`,
        `AMBIGUOUS_DOCUMENT_IDENTIFIER` (new `error_codes.py` entry),
        naming the matching `document_id`s so the caller can disambiguate.
      - `IndexResponse.document_id` already reports the real, resolved id
        - no contract change needed there; a caller using a filename
          finds out the real id from the response.
    - **User-visible behavior:** `POST /documents/JPMC Healthcare
      Benefits.pdf/index` (URL-encoded) behaves identically to using that
      document's real id, as long as exactly one current document has
      that name.
    - **Failure modes:** Ambiguous filename -> `409` naming the
      candidates, not a silent pick of "most recent" (explicit over
      implicit, matching this project's own established convention -
      `vector_db`, `chunking_strategy`, etc. are never silently guessed).
    - **Out of scope:** Filename lookup on `GET`/`DELETE
      /documents/{id}}` - only requested for reindex. `doc_classification`/
      `doc_type` as a lookup key (bulk-reindex-by-category is a different,
      unrequested operation).
    - **Open questions:** none.
  **Verified:** full suite green (118/118 - 5 new tests: filename resolves
  to the correct document_id and reindexes; two current documents sharing
  a filename is 409 naming both ids; unknown filename is still 404;
  filename resolution ignores a superseded document's old name while id
  lookup still reaches it regardless). Live-verified on the real dev DB:
  `JPMC Healthcare Benefits.pdf` genuinely resolves to 8 different current
  documents there (accumulated across this whole session's testing) and
  correctly 409s naming all 8 - confirming the ambiguity path against
  real, not synthetic, data. A fresh, unambiguous upload reindexed
  successfully by filename alone (real embedding call, 39 chunks, the
  response's `document_id` matching the actual uploaded id) - test
  document and its vectors cleaned up afterward. `README_TEST.md` (new
  4.12-4.14, plus a stale "now LlamaIndex's VectorStoreIndex" line fixed
  in the section intro while there) and the Postman `Index` folder (two
  new items) updated to match.

- [x] **Phase 26 (done, 2026-09-15) — Simplify: one ingestion endpoint,
  separate index/reindex endpoint removed.** Explicit user request:
  Phases 16/25's two-step upload-then-index design (built for dedup/re-
  index/cost-control reasons) was overengineered for a learning project
  with no production traffic - beginner-unfriendly complexity solving a
  problem this project doesn't have.

  - **Spec:** `POST /v1/rag-ingestion/documents` now does the whole
    pipeline per file in one call - save, extract, chunk (auto-selected
    strategy), embed, write to vector store - and returns one combined
    result per file (upload outcome + indexing outcome together).
    `POST /documents/{id}/index` (and filename-based reindex, Phase 25)
    removed - `routes_documents.py`'s `_index_document`/`index_document`/
    `_resolve_document_by_id_or_filename`/`_preflight_backends_ready`,
    `models/documents.py`'s `IndexRequest`/`IndexResponse`. Per-call
    chunking/embedding/vector_db overrides removed too - defaults only,
    no options surface to keep simple. Content-hash dedup (Phase 16) kept
    unchanged - a real, already-working check, not part of what was
    flagged as overengineered. `GET`/`DELETE /documents[/{id}]` unchanged.
  **Verified:** full suite green (113/113) - test_routes_documents.py
  rewritten with an autouse fake for `pipeline.index_document()` (no real
  embedding cost per test), every /index-specific test removed, upload
  tests updated to assert the now-combined result shape
  (`action`/`chunks_indexed`). Phase 24's regression test repointed at
  `/query` (still JSON-only) since its original target endpoint no longer
  exists - same bug class, still covered. Live-verified end to end with a
  real PDF: one `POST /documents` call did upload + real chunking (45
  chunks) + real embedding + real vector store write, response reported
  `action: "insert"`, `chunks_indexed: 45`; `GET` immediately after showed
  `status: "indexed"`; cleaned up via `DELETE`. `README_TEST.md` (section
  4 replaced with a short redirect, sections 2/3's stale "not indexed
  yet" language fixed) and Postman (`Index` sub-folder removed from `RAG
  Ingestion`; `Upload` item descriptions updated) updated to match.

- [x] **Phase 27 (done, 2026-09-15) — Delete-all-documents endpoint.**

  - **Spec:** `DELETE /v1/rag-ingestion/documents` (no id - the existing
    single-document delete is still `DELETE /documents/{id}`). Deletes
    every document's vectors, metadata row, and uploaded file - same
    full-delete semantics as the single version, just for all of them.
    `documents_service.delete_all_documents()` loops
    `list_documents()` + the existing `delete_document()` per row (no new
    deletion logic). Response: `documents_deleted`, `chunks_removed`
    (summed). Gated to `HR_SUPPORT` same as the rest of `RAG Ingestion`
    (router-level dependency, unchanged). No confirmation flag - matches
    this project's existing single-delete endpoint, which also has none.
  **Verified:** full suite green (114/114) - new test uploads 2 documents,
  calls delete-all, confirms `documents_deleted >= 2` and the list is
  empty afterward. Live/real run against the actual dev DB (not mocked)
  found and fixed a real bug: `delete_document()` returning `None` for a
  row already gone by the time the loop reached it crashed the whole
  batch (`TypeError` on `None["chunks_removed"]`) - now skipped instead,
  doesn't fail the rest. Postman gained a `Delete ALL documents` item.

- [x] **Phase 28 (done, 2026-09-15) — Fix: document_version reports 2 on
  a document's first-ever index.** Found live by the user testing upload.

  - **Spec:** `create_document()` inserts `document_version = 1`;
    `record_successful_index()` then does `document_version = document_version
    + 1` on *every* successful index, including the first. Since Phase 26
    fused upload+index into one call, a fresh document's first-ever index
    now always reports version 2, never 1 - confusing (`action: "insert"`
    alongside `document_version: 2` reads like something was indexed
    twice). Fix: `create_document()` inserts `document_version = 0`
    instead - "no successfully indexed version yet" - so the first
    successful index correctly lands on 1, and each subsequent re-index
    still increments normally (2, 3, ...). `sqlite_client.py` and
    `postgres_client.py` both change (same pattern, two backends).
    `documents_service.py`'s failure-path fallback (`index_outcome.get(
    "document_version", 1)`, used when indexing itself fails) changes to
    `0` too, matching what the row actually holds in that case.
    `DocumentRecord`/`DocumentUploadResult`'s field docs updated to match.
  **Verified:** new direct-SQLite regression test
  (`test_sqlite_client_document_version.py`, no HTTP/no embedding cost) -
  `create_document()` leaves `document_version=0`, first
  `record_successful_index()` returns 1, a second returns 2. Live-verified
  through the real API too: a fresh upload now returns
  `document_version: 1` (was 2). Full suite green (115/115).

- [x] **Phase 29 (done, 2026-09-15) — Suppress misleading pdfminer
  FontBBox console warning.** Root-caused live, not guessed at - traced
  to `pdfminer.pdffont` (a `pdfplumber` dependency, used by
  `table_extractor.py`), not this project's own code and not pypdf.

  - **Spec:** `table_extractor.py` sets `logging.getLogger("pdfminer")`'s
    level to `ERROR` at module import - this is the only file that uses
    `pdfplumber`. Harmless, known pdfminer quirk (a font missing a
    `FontBBox`, falls back to a default) - the warning itself is noise,
    not a real problem, so silencing it (not "fixing" pdfminer) is correct.
  **Verified:** live-ran `extract_tables_from_pdf()` against the exact PDF
  that showed the warning - no `FontBBox` message printed. Full suite
  green (115/115).

- [x] **Phase 30 (done, 2026-09-15) — Fix: running the test suite silently
  wiped the shared dev DB.** Found live - the user's own manually-uploaded
  test document 404'd, traced to `pytest` having deleted it.

  - **Spec:** `test_delete_all_removes_every_document` (Phase 27's test)
    called the *real* `DELETE /documents` endpoint against the real,
    shared dev SQLite DB - every `pytest` run wiped every document,
    including anything uploaded manually via Postman in between tool
    calls, with no warning. Rewritten to fake
    `documents_service.delete_all_documents()` (matching the existing
    query-route test pattern) and assert only that the route calls it and
    returns its result - real bulk-delete behavior is already covered by
    `delete_document()`'s own tests plus `delete_all_documents()`'s thin,
    obviously-correct loop over it.
  **Verified:** uploaded a real document, ran the full suite, confirmed
  the document still existed afterward (previously it would not have).
  Full suite still green (115/115).

- [x] **Phase 31 (2026-09-15) — ACTIVE_VECTOR_DB/ACTIVE_LLM_PROVIDER
  .env vars, one resolver helper each.**

  - **Spec:** `RAG_VECTOR_DB` renamed to `ACTIVE_VECTOR_DB` in `.env`; new
    `ACTIVE_LLM_PROVIDER` (default `openai`) for the LLM used in
    embedding/retrieval-time reasoning (not the final answer's model,
    which stays a separate, per-call override - unchanged). Two new
    helpers in `common/config/settings.py` -
    `get_active_vector_db(override)`/`get_active_llm_provider(override)` -
    replace the repeated `x or read_setting(None, "RAG_VECTOR_DB", ...)`/
    `llm_provider or "openai"` scattered across `ai/doc_processing/
    pipeline.py`, `ai/rag_pipeline/pipeline.py`,
    `ai/rag_pipeline/query_retrieval/retriever.py`, `common/clients/
    db_client/db_gateway.py`.
  **Verified:** all 5 call sites switched to the two new helpers; stale
  `RAG_VECTOR_DB` references in `models/rag.py`'s docstring and
  `vector_indexer.py`'s comment updated too. Full suite green (115/115).

- [x] **Phase 32 (2026-09-16) — Pilot: `RagQueryParams` dataclass
  replaces the repeated 10-field parameter list on the `/query` path.**

  - **Spec:** User-reported code smell - `routes_query.py`,
    `services/rag_service.py`, and `ai/rag_pipeline/pipeline.py`'s
    `answer_query()` each redeclare the same 10 parameters
    (query/top_k/vector_db/search_strategy/model_name/temperature/
    max_tokens/use_multi_query/use_self_query/llm_provider) - adding one
    field means editing 3 signatures. Deliberately scoped to this one
    payload only, as a pilot to review before considering it for
    `routes_documents.py`/`documents_service.py` - not applied there in
    this phase.
    - New `common/rag_query_params.py`: a plain `@dataclass` (not
      Pydantic) `RagQueryParams` with those 10 fields, same names/types/
      defaults as `RagQueryRequest`. Lives in `common/`, not `ai/`, so
      `routes_query.py` importing it does not become "routes importing
      ai/ directly" (CLAUDE.md's architecture rule) - it is a plain,
      framework-free data container, not pipeline logic.
    - `routes_query.py` builds one `RagQueryParams` from `payload` and
      calls `rag_service.answer_query(params)` - one argument, not 10.
    - `rag_service.answer_query(params: RagQueryParams)` passes `params`
      straight through to `pipeline.answer_query(params)` unchanged.
    - `ai/rag_pipeline/pipeline.py`'s `answer_query(params: RagQueryParams)`
      unwraps `params.*` at the top (where `resolved_vector_db`/
      `resolved_search_strategy`/`resolved_llm_provider` are already
      computed today) and calls the *unchanged* `retrieve_chunks()`/
      `generate_answer()` with the same individual arguments as today -
      those two functions are out of scope for this phase.
    - `retriever.py`, `routes_documents.py`, `documents_service.py`,
      `ai/doc_processing/pipeline.py` are explicitly **not** touched.
    - Tests: `tests/hrb_chatbot/api/rag/test_routes_query.py`'s
      `_fake_answer_query`/`_capturing_fake` helpers and
      `tests/hrb_chatbot/api/test_error_handling.py`'s
      `_fake_answer_query` updated to the new single-`params` signature -
      same assertions, same coverage, no behavior change.
  **Verified:** `code-reviewer` subagent run against the diff - bandit
  clean, no scope creep beyond the 6 listed files, no overengineering. Two
  findings addressed: docstring trimmed to CODING-STANDARDS' 2-line limit;
  the "same types as `RagQueryRequest`" spec wording was imprecise -
  `vector_db`/`search_strategy`/`llm_provider` stay `str | None` in the
  dataclass, matching the pre-existing convention already in
  `rag_service.py`/`pipeline.py` (enums live at the Pydantic/route
  boundary only, per `CLAUDE.md`'s architecture section - not a new
  deviation this phase introduced). Flagged, not fixed: no dedicated test
  file for the dataclass itself - it has no logic, and its field defaults
  are already exercised indirectly via
  `test_use_multi_query_and_use_self_query_default_to_false`. Full suite
  green (115/115).

- [x] **Phase 33 (2026-09-16) — Remove dead pass-through wrapper
  functions, both pipeline.py files.**

  - **Spec:** User-reported: `ai/rag_pipeline/pipeline.py`'s
    `retrieve_chunks()`/`generate_answer()` and `ai/doc_processing/
    pipeline.py`'s `index_chunks()` add nothing over the function they
    call - same signature, no resolved defaults, no transformation.
    Confirmed via grep: none of the three is imported or called from
    anywhere except the same file's own orchestrator function
    (`answer_query()`/`index_document()`), and no test references any of
    them directly. This is different from the service-layer thinness
    kept in Phase 32 (`rag_service.answer_query()` forwarding to
    `pipeline.answer_query()`) - that one is a real, documented layer
    boundary (routes never import `ai/` directly, per `CLAUDE.md`); these
    three are same-package indirection with no boundary to justify them.
    - `ai/rag_pipeline/pipeline.py`: delete `retrieve_chunks()` and
      `generate_answer()`; drop the `as _retrieve_chunks`/
      `as _generate_answer` import aliases (import the real names
      directly); `answer_query()` calls `retrieve_chunks()`/
      `generate_answer()` (the real functions) directly.
    - `ai/doc_processing/pipeline.py`: delete `index_chunks()`;
      `index_document()` calls `write_chunks()` (already imported)
      directly instead. `chunk_document()` is kept - it resolves
      `chunk_overlap`'s falsy-but-valid-zero default correctly (`if
      chunk_overlap is None` vs `or`), so it is not a pure pass-through.
    - No test changes expected - nothing references the removed names.
  **Verified:** grepped for any reference to the 3 removed names across
  `src/` and `tests/` before deleting - none found beyond the file that
  defined them. Full suite green (115/115) after removal.

  **Also checked, no change needed:** the ingestion path
  (`routes_documents.py` -> `documents_service.py` ->
  `pipeline.index_document()`) does not have Phase 32's
  repeated-10-parameter problem - the route only exposes `files`/
  `supersedes_document_id`; every other `index_document()` parameter
  (`vector_db`, `chunking_strategy`, etc.) is never set by a caller and
  always resolves from `.env`. Applying `RagQueryParams`-style there
  would add a class with no duplication to remove - flagged as
  considered, not a gap.

- [x] **Phase 34 (2026-09-16) — Simplify `retrieve_chunks()` to a
  single query; remove `decompose_query()`.**

  - **Spec:** User-reported: `retriever.py`'s `retrieve_chunks(queries:
    list[str], ...)` loops over multiple queries and dedupes results by
    `(document_id, chunk_index)` - scaffolding for Phase 5.1's real query
    decomposition. `pipeline.py`'s `decompose_query()` is the only
    caller's source of that list, and it is a documented MVP placeholder
    that always returns `[query]` (one item). Today the loop always runs
    once and the dedup set never removes anything - real complexity for
    a feature that does not exist yet, same category of issue as Phase
    33. Confirmed via grep: `decompose_query` and `retrieve_chunks` have
    no other callers.
    - `retriever.py`: `retrieve_chunks(query: str, ...)` - drop the outer
      loop and `seen_chunk_keys` dedup set; call the search
      function/`search_multi_query` once with `query` directly; Self-
      Query's `queries[0]` becomes plain `query`. `search_multi_query()`
      itself is untouched - its own dedup handles LangChain's internal
      rewritten-query fan-out (`use_multi_query=True`), a separate,
      still-active mechanism from `decompose_query()`.
    - `pipeline.py`: delete `decompose_query()` (removing the outer loop
      makes it a pure identity call - the same dead-wrapper pattern
      Phase 33 already removed elsewhere); `answer_query()` passes
      `params.query` to `retrieve_chunks()` directly. Module docstring's
      reference to `decompose_query()` updated.
    - Tests: `test_retriever.py`'s ~13 `retrieve_chunks([...])` calls
      become `retrieve_chunks(...)` (plain string, not a list).
      `test_the_same_chunk_found_by_two_subqueries_is_not_duplicated`
      tests exactly the multi-query dedup path being removed - deleted,
      not adapted (the scenario it names, "two subqueries," can no
      longer occur once the outer loop is gone). Real dedup coverage for
      the still-active `use_multi_query` path stays via
      `test_search_multi_query_merges_and_dedupes_across_rewritten_queries`,
      untouched.
    - When Phase 5.1's real decomposition ships, `retrieve_chunks()`
      regains a list parameter and a real caller then - not built ahead
      of that need now.
  **Verified:** `code-reviewer` subagent run against the diff - bandit
  clean, scope matched the spec, `decompose_query()` fully gone (grepped),
  no overengineering. One finding fixed: `answer_query()`'s own docstring
  still said "decompose, retrieve, generate" after the module-level
  docstring was already updated - reworded to "retrieve, generate." Full
  suite green (114/114).

## Verification checklist (Phases 1-3)

1. `GET /health?deep=true` → vector + metadata database checks healthy. **Done.**
2. `POST /rag/documents` with a real PDF from `resources/kb_docs/` → 200,
   document id returned, file in `data/uploads/`, SQLite row exists. **Done**,
   including the batch partial-success case.
3. `POST /rag/documents/{id}/index` → clear `NotImplementedError` naming
   `ai/doc_processing/`, not a crash.
4. `POST /rag/query` → same stubbed-but-clear behavior, naming
   `ai/rag_pipeline/`.
