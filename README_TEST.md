# API test guide

Manual test cases for every endpoint this project currently has, each with a
real command, the payload it sends, and what to expect back. Every example
targets the server running locally (`http://127.0.0.1:8093`, per
`README.md`'s run instructions) - swap the host for the App Runner URL to run
the same cases against the deployed instance.

Cases are grouped **happy path** (the normal, working case) and **unhappy /
edge** (what should happen when something is wrong) per endpoint, because a
contract that only documents success hides exactly the behavior callers rely
on when things go wrong - a `POST /v1/rag/documents` that silently 500s on an
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

No case here spends money by accident - `?deep=true` on `/health` and
`POST /v1/rag/documents/{id}/index` are the only ones that call a real
provider, called out explicitly where they appear.

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

## 1. Health - `GET /health`

### Happy path

**1.1 Shallow check (default, instant, no network, free)**
```
curl "http://127.0.0.1:8093/health"
```
Expect `200` if every configured provider has its settings present, `503`
otherwise - shallow checks configuration only, so `200` here does not yet
prove any key or connection actually works.

**1.2 Deep check against the default LLM (spends nothing - `GET /models` is free)**
```
curl "http://127.0.0.1:8093/health?deep=true"
```
Expect `200`, `checks.llm.status: "healthy"`, a real `models_visible` count.

**1.3 Deep check against a specific provider + vector store + metadata store**
```
curl "http://127.0.0.1:8093/health?deep=true&provider=anthropic&vector_provider=pinecone&metadata_provider=postgres"
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
`check_llm()` falls into its `else` branch (treats anything not
`anthropic`/`openrouter`/`bedrock` as `openai`) rather than rejecting the
name - expect `200`/`503` based on OpenAI's own status, **not** a 400. Worth
knowing this is silent, unlike the vector/metadata switches below.

**1.5 Unknown vector_provider (does reject, unlike 1.4)**
```
curl "http://127.0.0.1:8093/health?deep=true&vector_provider=made_up_store"
```
`check_vector_database()` only branches on `"pinecone"` vs. everything else
falling to Chroma - same silent-fallback behavior as 1.4, not a validation
error. Contrast this with `RAG_VECTOR_DB` itself (settings-driven, not this
query param), which does raise on an unknown name - see `db_gateway.py`.

**1.6 deep=true when a provider's key is deliberately blank**
Temporarily unset `TAVILY_API_KEY` in `.env` (Tavily has no `/health`
route wired in yet - see `docs/BACKLOG.md` - so this specific case does not
apply to any live endpoint today; listed as a known gap, not a case you can
currently exercise).

---

## 2. Document upload - `POST /v1/rag/documents`

### Happy path

**2.1 Upload a single real PDF**
```
curl -F "files=@resources/kb_docs/JPMC Healthcare Benefits.pdf;type=application/pdf" \
  http://127.0.0.1:8093/v1/rag/documents
```
Expect `200`, `uploaded_count: 1`, `rejected_count: 0`, one `results` entry
with `status: "uploaded"` and a real `document_id` (a hex uuid). Save that id
- every later example in this file reuses it.

**2.2 Batch upload, multiple valid PDFs in one call**
```
curl \
  -F "files=@resources/kb_docs/JPMC Paid TimeOff.pdf;type=application/pdf" \
  -F "files=@resources/kb_docs/JPMC Guild Tuition Assistance.pdf;type=application/pdf" \
  http://127.0.0.1:8093/v1/rag/documents
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
  http://127.0.0.1:8093/v1/rag/documents
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
curl -F "files=@empty_scratch.pdf;type=application/pdf" http://127.0.0.1:8093/v1/rag/documents
rm empty_scratch.pdf
```
Verified live: `200`, `rejected_count: 1`, error `"File is empty"`.

**2.5 File over the 20MB limit**
```
head -c 21000000 /dev/urandom > too_big_scratch.pdf
curl -F "files=@too_big_scratch.pdf;type=application/pdf" http://127.0.0.1:8093/v1/rag/documents
rm too_big_scratch.pdf
```
Verified live: `200`, `rejected_count: 1`, error
`"File is 21000000 bytes, which exceeds the 20971520-byte limit"`. (This is
real random bytes, not a real PDF - the content-type check happens before
any PDF-structure check, so this is rejected on size, not on being invalid
PDF content - both would reject it either way.)

**2.6 No `files` field at all**
```
curl -X POST http://127.0.0.1:8093/v1/rag/documents
```
Expect `422` (FastAPI's own request-validation error, before this project's
code ever runs) - `files` is a required field with no default.

---

## 3. List / get documents - `GET /v1/rag/documents`, `GET /v1/rag/documents/{id}`

### Happy path

**3.1 List every uploaded document**
```
curl http://127.0.0.1:8093/v1/rag/documents
```
Expect `200`, `count` matching the real number of rows, newest first.

**3.2 Get one document by its real id** (use an id from section 2)
```
curl http://127.0.0.1:8093/v1/rag/documents/<document_id>
```
Expect `200` and the full `DocumentRecord` - `status` will be `"uploaded"`
until section 4 indexes it, `chunk_ids: null` until then too.

### Unhappy / edge cases

**3.3 Unknown document id**
```
curl -i http://127.0.0.1:8093/v1/rag/documents/does-not-exist
```
Expect `404`, body `{"error": "Unknown document 'does-not-exist'"}` -
`-i` here so the status code is visible, since the body alone looks the
same shape as a real error would.

**3.4 Path-traversal-looking id**
```
curl -i "http://127.0.0.1:8093/v1/rag/documents/..%2F..%2Fetc%2Fpasswd"
```
Verified live: expect `404` with FastAPI's own generic
`{"detail":"Not Found"}` - the encoded slashes never even reach this
project's route handler, because `document_id` is declared as a single
path segment and FastAPI's router itself rejects anything containing `/`
before any application code runs. Stronger than the "reaches the handler,
gets looked up, comes back unknown" case in 3.3 - worth knowing these are
two different 404s for two different reasons, not the same code path.

---

## 4. Index a document - `POST /v1/rag/documents/{id}/index`

**Spends money**: this calls the real embedding model
(`OPENAI_EMBED_MODEL`, default `text-embedding-3-small`) for every chunk of
the document. Cheap for one small PDF, but not free - don't loop this over
every file in `resources/kb_docs/` without meaning to.

### Happy path

**4.1 Index with every default (no body at all)**
```
curl -X POST http://127.0.0.1:8093/v1/rag/documents/<document_id>/index
```
Expect `200`, `action: "insert"` (first time), `chunks_indexed` > 0,
`chunks_removed: 0`, and `vector_db`/`embedding_model`/`chunk_size`/
`chunk_overlap` echoing back whatever `.env` currently defaults to.

**4.2 Re-index the same document (this must report `update`, not `insert`)**
```
curl -X POST http://127.0.0.1:8093/v1/rag/documents/<document_id>/index
```
Expect `200`, `action: "update"` this time - confirms the insert/update
logic in `vector_indexer.py` is actually distinguishing the two cases, not
just always inserting.

**4.3 Per-call override of chunk size/overlap and vector store**
```
curl -X POST http://127.0.0.1:8093/v1/rag/documents/<document_id>/index \
  -H "Content-Type: application/json" \
  -d '{"chunk_size": 500, "chunk_overlap": 50, "vector_db": "chromadb"}'
```
Expect `200`, response's `chunk_size`/`chunk_overlap`/`vector_db` reflecting
exactly these overrides, not `.env`'s defaults - this is what proves the
override is real per-call config, not just accepted and ignored.

### Unhappy / edge cases

**4.4 Index an unknown document id**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/documents/does-not-exist/index
```
Expect `404` before any embedding call is even attempted - confirm this by
checking your OpenAI usage dashboard doesn't move, not just by reading the
status code.

**4.5 `chunk_overlap >= chunk_size` (must be rejected before any provider call)**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/documents/<document_id>/index \
  -H "Content-Type: application/json" \
  -d '{"chunk_size": 200, "chunk_overlap": 200}'
```
Expect `422` - `IndexRequest`'s own `model_validator` in `models/documents.py`
rejects this at the request-parsing layer, before the route body even runs.

**4.6 `chunk_size` outside the allowed range**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/documents/<document_id>/index \
  -H "Content-Type: application/json" \
  -d '{"chunk_size": 50}'
```
Expect `422` - `chunk_size` has `ge=100` in the model, `50` is below it.

**4.7 Unknown `vector_db` name**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/documents/<document_id>/index \
  -H "Content-Type: application/json" \
  -d '{"vector_db": "made_up_store"}'
```
Expect `500` with `db_gateway.py`'s own `ValueError` message in the body
(`"Unknown vector store 'made_up_store' - use 'chromadb' or 'pinecone'"`) -
this one *is* rejected, unlike the health-check query params in 1.4/1.5,
because this path goes through `vector_store(provider=...)` directly.

---

## 5. RAG query - `POST /v1/rag/query`

**Not implemented yet** - Phase 6 (retrieval + grounded generation) is
hand-written and still 📋 planned, per `docs/RAG-ROADMAP.md`. Every case
below documents today's stubbed behavior, which is intentional, not a bug.

### "Happy" path (for a stub, this means: fails the right way)

**5.1 A well-formed query against the stub**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many vacation days do I get?", "top_k": 5}'
```
Expect `501`, body naming `ai/rag_pipeline/pipeline.py` as the module to
implement - **not** a `500` or a `200` with a fake answer. Once Phase 6
lands, this exact call becomes the real happy-path case with a genuine
`answer` and non-empty `sources`.

### Unhappy / edge cases (still meaningful against a stub)

**5.2 Empty query string**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": ""}'
```
Expect `422` - `RagQueryRequest.query` has `min_length=1`, so this never
reaches the stub at all. Confirms request validation doesn't wait on Phase 6
to exist.

**5.3 `top_k` outside the allowed range**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 100}'
```
Expect `422` - `top_k` has `le=20`.

**5.4 Missing `query` field entirely**
```
curl -i -X POST http://127.0.0.1:8093/v1/rag/query -H "Content-Type: application/json" -d '{}'
```
Expect `422` - `query` has no default.

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
be exercised yet either - `POST /v1/rag/query` is still the Phase 6 stub (see
case 5.1 above) - it exists now so it's ready the moment Phase 6 lands.

For Postman-based manual testing, `postman/hrb_chatbot.postman_collection.json`
covers every case in this file as importable requests.
