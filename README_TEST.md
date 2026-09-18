# API test guide

Manual test cases for every endpoint this project currently has, each with a
real command, the payload it sends, and what to expect back. Every example
targets the server running locally (`http://127.0.0.1:8093`, per
`README.md`'s run instructions) - swap the host for the App Runner URL to run
the same cases against the deployed instance.

Cases are grouped **happy path** (the normal, working case) and **unhappy /
edge** (what should happen when something is wrong) per endpoint, because a
contract that only documents success hides exactly the behavior callers rely
on when things go wrong - a `POST /v1/rag-ingestion/documents` that silently 500s on an
empty batch is a worse API than one that returns a clear 4xx, and the only
way to know which this one does is to have actually tried it.

Real files under `resources/kb_docs/` are used as sample data rather than
invented ones, so these commands are copy/paste runnable as-is:

```
resources/kb_docs/JPMC Empower 401(k) Savings Plan.pdf
resources/kb_docs/JPMC Guild Tuition Assistance.pdf
resources/kb_docs/JPMC Healthcare Benefits.pdf
resources/kb_docs/JPMC Paid TimeOff.pdf
resources/kb_docs/JPMC Sedgwick Unpaid Timeoff.pdf
resources/kb_docs/JPMC Unpaid TimeOff.pdf
```

No case here spends money by accident - `GET /health` (always a real,
though free, provider call now - see section 1) and
`POST /v1/rag-ingestion/documents/{id}/index` are the only ones that call a
real provider, called out explicitly where they appear.

**Gateway headers required (Phase 23, 2026-09-15)**: every `/v1/rag-ingestion/*`
and `/v1/rag-retrieval/*` call below needs three identity headers, or it's a
`401`. This is a **placeholder for real OAuth, not real security** - the
values are read as-is, unsigned, trivially spoofable; the point is the
role-gate wiring (`api/gateway/`) real auth slots into later, not
authentication today. `GET /ping`/`GET /health` need none of this. Add
these to every ingestion (`-H "X-Role: hr_support"` - the only role allowed
to upload/list/get/delete/index) and retrieval (`employee`, `manager`, or
`hr_support` - all three, uniformly) command below:
```
# Ingestion (section 2-4) - HR_SUPPORT only
-H "X-Employee-Id: E00001" -H "X-Full-Name: Hana Support" -H "X-Role: hr_support"

# Retrieval (section 5) - employee, manager, or hr_support
-H "X-Employee-Id: E00002" -H "X-Full-Name: Eddy Employee" -H "X-Role: employee"
```

**Git Bash note**: every case below was run and verified against a live
local server. A few needed one adjustment along the way - Git Bash's MSYS
layer silently mangles `-F` file arguments that start with an absolute
Unix-style path (`/tmp/...`), corrupting the request before curl even sees
it (confirmed: `curl: (26) Failed to open/read local data from
file/application` on a perfectly valid file). The fix, already applied
below, is to create scratch files as **relative paths inside the repo**
instead of under `/tmp` - `resources/kb_docs/...` paths were never affected
either way, only invented `/tmp` scratch files were. If you're on a real
Unix shell (not Git Bash on Windows) this note doesn't apply to you.

---

## 1. Health - `GET /ping`, `GET /health`

Two endpoints, two jobs, not one endpoint with a toggle (the old `?deep=true`
query param is gone - see `CLAUDE.md`'s SDD section for why).

### Happy path

**1.1 Liveness only - instant, no network, no cost**
```
curl "http://127.0.0.1:8093/ping"
```
Expect `200`, `{"status": "ok"}` - this only confirms the process is up, it
never calls any backend. What a container `HEALTHCHECK` or a deploy's
smoke test should use, not `/health`.

**1.2 The real diagnostic - always makes one free call per backend**
```
curl "http://127.0.0.1:8093/health"
```
Expect `200`, `checks.llm.status: "healthy"`, a real `models_visible` count -
`GET /health` always does the real check now, no query param needed.

**1.3 Check a specific provider + vector store + metadata store**
```
curl "http://127.0.0.1:8093/health?provider=anthropic&vector_provider=pinecone&metadata_provider=postgres"
```
Expect `200` if all three backends are actually reachable. This is the
single call that answers "is everything wired up right now" - see
`docs/RAG-ROADMAP.md`'s Phase 10 section for why `metadata_provider=postgres`
specifically depends on Neon existing.

### Unhappy / edge cases

**1.4 Unknown provider name**
```
curl "http://127.0.0.1:8093/health?provider=made_up_provider"
```
Expect `422` naming the valid options (`'openai', 'anthropic', 'openrouter'
or 'bedrock'`) - `provider`/`vector_provider`/`metadata_provider` are all
real enums now (`common/enums.py`), rejected at the API boundary, not a
silent fallback to the default.

**1.5 Unknown vector_provider - same rejection, not a special case anymore**
```
curl "http://127.0.0.1:8093/health?vector_provider=made_up_store"
```
Expect `422`. All three provider query params behave identically now -
there's no longer a "some reject, some don't" distinction to contrast.

**1.6 A provider's key is deliberately blank**
```
curl "http://127.0.0.1:8093/health"
```
Temporarily unset `OPENAI_API_KEY` in `.env` and restart the server first.
Expect `503` (overall status is unhealthy if any one check is), with
`checks.llm` reporting `{"status": "unhealthy", "message": "API key not
configured"}` - a missing key surfaces as a clear message in the response
body, not a crash (`health_check()` never raises - see
`docs/CODING-STANDARDS.md`).

**1.7 Gateway access control (Phase 23) - missing/wrong role**
```
curl -i http://127.0.0.1:8093/v1/rag-ingestion/documents
```
Verified live: `401`, `code: "UNAUTHENTICATED"`, error naming which
header(s) are missing (`X-Employee-Id`, `X-Full-Name`, `X-Role`).
```
curl -i http://127.0.0.1:8093/v1/rag-ingestion/documents \
  -H "X-Employee-Id: E00002" -H "X-Full-Name: Eddy Employee" -H "X-Role: employee"
```
Verified live: `403`, `code: "FORBIDDEN"` - only `hr_support` may reach
`/v1/rag-ingestion/*`; `/v1/rag-retrieval/*` accepts `employee`, `manager`,
or `hr_support` uniformly. `GET /ping`/`GET /health` need no headers at all.

---

## 2. Document upload - `POST /v1/rag-ingestion/documents`

**Spends money (Phase 26, 2026-09-15)**: upload now chunks, embeds, and
indexes each file in the same call - real embedding calls, not free. Cheap
for one small PDF, but don't loop this over every file in
`resources/kb_docs/` without meaning to.

### Happy path

**2.1 Upload a single real PDF**
```
curl -F "files=@resources/kb_docs/JPMC Healthcare Benefits.pdf;type=application/pdf" \
  http://127.0.0.1:8093/v1/rag-ingestion/documents
```
Expect `200`, `uploaded_count: 1`, `rejected_count: 0`, one `results` entry
with `status: "uploaded"`, a real `document_id` (a hex uuid), and (Phase
26) `action: "insert"`, `chunks_indexed` > 0 - it's indexed already, not a
separate step. Save the id - every later example in this file reuses it.

**2.2 Batch upload, multiple valid PDFs in one call**
```
curl \
  -F "files=@resources/kb_docs/JPMC Paid TimeOff.pdf;type=application/pdf" \
  -F "files=@resources/kb_docs/JPMC Guild Tuition Assistance.pdf;type=application/pdf" \
  http://127.0.0.1:8093/v1/rag-ingestion/documents
```
Expect `200`, `uploaded_count: 2`, `rejected_count: 0`, two `results` entries
in the order given.

### Unhappy / edge cases

**2.3 Batch upload where one file is invalid - the other must still succeed**
```
echo "not a pdf" > not_a_pdf_scratch.txt
curl \
  -F "files=@resources/kb_docs/JPMC Unpaid TimeOff.pdf;type=application/pdf" \
  -F "files=@not_a_pdf_scratch.txt;type=text/plain" \
  http://127.0.0.1:8093/v1/rag-ingestion/documents
rm not_a_pdf_scratch.txt
```
Expect `200` (not a batch-level failure), `uploaded_count: 1`,
`rejected_count: 1` - the second result has `status: "rejected"`,
`document_id: null`, and an `error` naming the wrong content type. This is
the single most important behavior to verify in this endpoint - see
`models/documents.py`'s own docstring on why a batch is not all-or-nothing.

**2.4 Empty file**
```
touch empty_scratch.pdf
curl -F "files=@empty_scratch.pdf;type=application/pdf" http://127.0.0.1:8093/v1/rag-ingestion/documents
rm empty_scratch.pdf
```
Verified live: `200`, `rejected_count: 1`, error `"File is empty"`.

**2.5 File over the 20MB limit**
```
head -c 21000000 /dev/urandom > too_big_scratch.pdf
curl -F "files=@too_big_scratch.pdf;type=application/pdf" http://127.0.0.1:8093/v1/rag-ingestion/documents
rm too_big_scratch.pdf
```
Verified live: `200`, `rejected_count: 1`, error
`"File is 21000000 bytes, which exceeds the 20971520-byte limit"`. (This is
real random bytes, not a real PDF - the content-type check happens before
any PDF-structure check, so this is rejected on size, not on being invalid
PDF content - both would reject it either way.)

**2.6 No `files` field at all**
```
curl -X POST http://127.0.0.1:8093/v1/rag-ingestion/documents
```
Expect `422` (FastAPI's own request-validation error, before this project's
code ever runs) - `files` is a required field with no default.

**2.7 Re-uploading identical content (dedup reinstated 2026-09-14, Phase 16)**
```
curl -F "files=@resources/kb_docs/JPMC Healthcare Benefits.pdf;type=application/pdf" \
  http://127.0.0.1:8093/v1/rag-ingestion/documents
```
Run the exact same command a second time. First call: `200`,
`uploaded_count: 1`, a real `document_id`. Second call (identical bytes):
`200`, `uploaded_count: 0`, `duplicate_count: 1`, the *same* `document_id`
as the first call, `status: "duplicate"`, `message` naming which existing
document it matched - no second document is created. Uploading the same
content under a *different* filename is still a duplicate (byte content is
what's hashed, not the name); uploading genuinely *different* content
always creates a new document, same filename or not. The
`Idempotency-Key` header cache is still removed (a separate mechanism,
deferred pending a real Redis-backed store - see `docs/BACKLOG.md`) - this
case is specifically about content-hash duplicate detection, which is back.

---

## 3. List / get / delete documents - `GET /v1/rag-ingestion/documents`, `GET /v1/rag-ingestion/documents/{id}`, `DELETE /v1/rag-ingestion/documents/{id}`

### Happy path

**3.1 List every uploaded document**
```
curl http://127.0.0.1:8093/v1/rag-ingestion/documents
```
Expect `200`, `count` matching the real number of rows, newest first.

**3.2 Get one document by its real id** (use an id from section 2)
```
curl http://127.0.0.1:8093/v1/rag-ingestion/documents/<document_id>
```
Expect `200` and the full `DocumentRecord` - `status: "indexed"` and real
`chunk_ids` already, since upload indexes in the same call (Phase 26).

### Unhappy / edge cases

**3.3 Unknown document id**
```
curl -i http://127.0.0.1:8093/v1/rag-ingestion/documents/does-not-exist
```
Expect `404`, body `{"error": "Unknown document 'does-not-exist'"}` -
`-i` here so the status code is visible, since the body alone looks the
same shape as a real error would.

**3.4 Path-traversal-looking id**
```
curl -i "http://127.0.0.1:8093/v1/rag-ingestion/documents/..%2F..%2Fetc%2Fpasswd"
```
Verified live: expect `404` with FastAPI's own generic
`{"detail":"Not Found"}` - the encoded slashes never even reach this
project's route handler, because `document_id` is declared as a single
path segment and FastAPI's router itself rejects anything containing `/`
before any application code runs. Stronger than the "reaches the handler,
gets looked up, comes back unknown" case in 3.3 - worth knowing these are
two different 404s for two different reasons, not the same code path.

**3.5 Delete a document (full delete: vectors + metadata + file), added 2026-09-10**
```
curl -i -X DELETE http://127.0.0.1:8093/v1/rag-ingestion/documents/<document_id>
```
Expect `200`, `{"document_id": ..., "filename": ..., "chunks_removed": N}`
(`N` is `0` if it was never indexed). Verified live against real data: an
indexed document with 40 real chunks in ChromaDB was deleted, confirmed via
a direct collection query that the vector store's total count dropped by
exactly 40, the document's `GET` now returns `404`, and its
`data/uploads/{id}/` directory is gone from disk. This is a **full**
delete, not selective - a document has one current state, not a retained
version history to pick a version from (`document_version` is a counter,
not stored history).

**3.6 Delete an unknown id**
```
curl -i -X DELETE http://127.0.0.1:8093/v1/rag-ingestion/documents/does-not-exist
```
Expect `404`, same `{"error": "Unknown document '...'"}` shape as 3.3.

---

## 4. Indexing - folded into upload (Phase 26, 2026-09-15)

There is no longer a separate index/reindex endpoint. `POST
/v1/rag-ingestion/documents` (section 2) now does the whole pipeline in one
call - save, extract, chunk (auto-selected strategy, no per-call
overrides), embed, write to the vector store - and reports the outcome
(`action`, `chunks_indexed`, `chunks_removed`) directly in each upload
result. `.../documents/{id}/index` is a plain `404` now, same as any
unmatched path.

Per-call chunking/embedding/vector_db overrides and filename-based
reindex (Phase 25) were removed along with the endpoint, to keep this a
simpler, learning-focused surface (this project doesn't run in production,
so the config-flexibility those existed for wasn't earning its complexity)
- see `docs/RAG-ROADMAP.md`'s Phase 26 entry.

---

## 5. RAG query - `POST /v1/rag-retrieval/query`

**Real retrieval + grounded generation, as of 2026-09-10** (Phase 6 MVP,
Claude-Code override - see `docs/RAG-ROADMAP.md`). Query decomposition,
guardrails, and evaluations are still hand-written and not built. A
well-formed query spends one real embedding call + one real chat
completion - requires the target document to already be indexed.

### Happy path

**5.1 A well-formed query against a real, indexed document**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many weeks of paid time off do employees get per year?", "top_k": 5}'
```
Expect `200`, a real `answer` grounded in the actual chunk text, `sources`
with real `filename`/`chunk_index`/`score` entries, and `model_used`
naming the model that actually generated the answer. Verified live: asked
against the indexed `JPMC Paid TimeOff.pdf`, returned "3 to 5 weeks of
vacation annually based on years of service and pay grade" - traceable
directly to the retrieved chunk text. Querying against a knowledge base
with no relevant indexed content returns a fixed "I don't have any
information about that" answer with empty `sources`, without spending an
LLM call.

**5.5 MMR search via `search_strategy` in the request body**
```
curl -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many weeks of paid time off do employees get per year?", "top_k": 3, "search_strategy": "mmr"}'
```
Expect `200`, `search_strategy: "mmr"`, `score: null` on every source
(LangChain's `max_marginal_relevance_search()` doesn't return a per-chunk
score) - and, compared to 5.1's plain similarity search, sources drawn
from more distinct documents rather than several near-duplicate chunks of
the same one. Verified live: the exact same question returned 2 chunks
from one document under plain similarity, vs. 3 chunks from 3 different
documents under MMR. **This is now the only way to select MMR** - the old
dedicated `POST /query/mmr` endpoint was removed in Phase 21 (2026-09-14);
see `docs/RAG-ROADMAP.md`'s Phase 21 entry for why.

**5.6 Omitting `search_strategy` - defaults to similarity**
```
curl -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```
Expect `200`, `search_strategy: "similarity"` in the response - the
default, unchanged behavior when the field is left out.

**5.8 `use_multi_query: true` - rewrites the question, merges results (Phase 20)**
```
curl -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How does 401k vesting work?", "use_multi_query": true, "top_k": 5}'
```
A layer on top of `search_strategy` (similarity or MMR), not a third
option - LangChain's own `MultiQueryRetriever` rewrites the question into
several phrasings, searches with each, and merges/dedupes the results, so
more candidate chunks get considered before the same `top_k` is returned.
Every source's `score` is null (`MultiQueryRetriever` doesn't return one,
same as MMR). Verified live against a real indexed 401(k) document:
returned 7 real chunks and a grounded answer, spending one extra real LLM
call (the rewrite) plus one embedding+search per rewritten phrasing.

**5.9 `use_self_query: true` - the model parses a metadata filter from the question (Phase 20)**
```
curl -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me benefits-type documents about 401k matching", "use_self_query": true, "top_k": 5}'
```
LangChain's own `SelfQueryRetriever` parses the question into a structured
filter over `doc_type`/`department`/`doc_classification` (Phase 19's chunk
metadata) before searching - `is_current` is never exposed to it, and
always stays AND-ed on regardless of what gets parsed (verified directly:
a superseded chunk matching the parsed filter is still excluded). The
response's `applied_filter` shows exactly what was parsed, or `null` if
nothing was found to filter on or parsing failed (falls back to an
unfiltered search, never errors). **A real, honest limitation found during
live verification, not a bug:** `doc_type` is semi-controlled (extraction
picks from a short fixed list) and filters reliably - isolated live,
`doc_type=benefits` alone matched 5 real chunks. `doc_classification` is
deliberately free text (Phase 19's own design), so an exact-match `$eq`
filter on it only succeeds when the model's guess happens to match the
stored string exactly - e.g. it reliably guesses `doc_classification:
"401k"` for a 401k question, but a real document's actual extracted value
was `"401(k) Savings Plan"`, so that filter alone matches zero chunks even
though relevant ones exist. See `docs/BACKLOG.md`'s "Retrieval quality"
section for the tracked follow-up.

**5.10 `llm_provider` - which model powers `use_multi_query`/`use_self_query`'s own reasoning**
```
curl -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "use_multi_query": true, "llm_provider": "anthropic"}'
```
Defaults to `openai` when omitted. Independent of `model_name` - which
still only ever controls the final answer's model (always OpenAI today,
unchanged by this phase; see `docs/FAQ.md`). An unknown value (e.g.
`"llm_provider": "made-up"`) is a `422` - real `LlmProvider` enum, same
pattern as `vector_db`/`search_strategy`.

### Unhappy / edge cases (validation - unchanged by Phase 6 landing)

**5.2 Empty query string**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": ""}'
```
Expect `422` - `RagQueryRequest.query` has `min_length=1`, so this never
reaches the stub at all. Confirms request validation doesn't wait on Phase 6
to exist.

**5.3 `top_k` outside the allowed range**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 100}'
```
Expect `422` - `top_k` has `le=20`.

**5.4 Missing `query` field entirely**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag-retrieval/query -H "Content-Type: application/json" -d '{}'
```
Expect `422` - `query` has no default.

**5.7 Unknown `search_strategy`**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "search_strategy": "not-a-real-strategy"}'
```
Expect `422`, naming the unknown strategy and listing the valid ones.

**5.11 Unknown `llm_provider` (Phase 20)**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag-retrieval/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "llm_provider": "made-up"}'
```
Expect `422` - real `LlmProvider` enum, naming the unknown value.

---

## Golden dataset

**Yes, as of 2026-09-08** - `resources/golden_dataset/golden_dataset.json`,
22 real question → expected-answer/expected-source cases, every fact pulled
directly from the actual text of the PDFs in `resources/kb_docs/` (read in
full, not summarized from memory) - 18 grounded happy-path questions across
all six documents, 1 cross-document synthesis case, and 3 adversarial/
out-of-scope cases (a question the knowledge base can't answer at all, a
number the source document genuinely doesn't state, and a false-premise
question that should be corrected, not agreed with).

This is a **one-time override** of Phase 8's hand-written boundary in
`docs/RAG-ROADMAP.md` - the same kind of explicit, requested exception
Phase 4 (chunking/embedding/indexing) was, not a new precedent for the rest
of Phase 8 (retrieval metrics, LLM-as-judge evaluation, A/B testing
infrastructure), which remain hand-written and unbuilt. The dataset can't
be exercised yet either - `POST /v1/rag-retrieval/query` is still the Phase 6 stub (see
case 5.1 above) - it exists now so it's ready the moment Phase 6 lands.

For Postman-based manual testing, `postman/hrb_chatbot.postman_collection.json`
covers every case in this file as importable requests.
