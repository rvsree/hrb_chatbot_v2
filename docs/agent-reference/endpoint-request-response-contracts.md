# Endpoint Request/Response Contracts

Source of truth for each endpoint's finalized request, response, and error
shape - written and confirmed here **before** any code changes, so a
contract never has to be re-derived from scattered conversation. When
implementing, match this file exactly; if a contract needs to change,
update this file first, then the code.

Status per endpoint is marked below. Only what's marked **Finalized** has
been confirmed - everything else is not yet agreed and must not be
implemented yet.

## Identity source: JSON payload on every endpoint, never headers, never query params

Confirmed 2026-09-20 (final form): every endpoint that does RBAC takes a
JSON body with a `user_profile` sub-object, including `GET`/`DELETE` -
non-standard HTTP (a body on `GET`/`DELETE`), a deliberate choice so there
is exactly one identity mechanism everywhere, not two. `X-Employee-Id`/
`X-Full-Name`/`X-Role` headers and query-param identity were both tried
and rejected during this design pass - neither is used anywhere.

- `DELETE .../{id}`, `DELETE .../documents`, `DELETE /v1/conversations/{id}`
  (all): body is `{"user_profile": {...}}` only - no other fields.
- `POST` endpoints (upload, query): `user_profile` is one sub-object
  alongside the endpoint's other fields, same as already documented below.
- `GET /health`/`GET /ping` stay exactly as they are - no identity, no
  RBAC. Confirmed: they're called by automated infrastructure (Docker
  `HEALTHCHECK`, CI smoke test), not an employee acting on data.

**Revised 2026-10-06 (Phase 96), for `GET` only:** `GET /v1/genai-rag/
ingest-document/documents`, `GET .../{id}`, and `GET .../documents/
cleanup/preview` now take identity as **query params**
(`?employee_id=...&full_name=...&role=...`), not a body - confirmed, not
guessed, that the Fetch spec forbids a body on `GET`/`HEAD` (`fetch()`
throws `TypeError: Request with GET/HEAD method cannot have body` before
any network call reaches the server), so a real browser client -
`hrb_chatbot_ui` - could never call the 2026-09-20 shape above as
written. This is **not** a reversal of the header/query-param rejection
above for `POST`/`DELETE` - those keep the body exactly as decided; this
is new information specific to `GET` that the original design pass
didn't have. `api/gateway/rbac.py`'s `identity_from_query_params()`
builds the same `UserProfile` either way, then hands it to the same
unchanged `require_role()` - 401/403 behavior is identical, only the
transport differs.

**Known, accepted tradeoff, on record per the 2026-09-20 security review:**
`role` now comes from the same payload/query-params as the action it
gates, so `require_role()` can't stop anyone who knows the field name - RBAC
here is a formality, not a real control, once this ships. Matches this
project's existing placeholder-auth stage (real OAuth was always the
eventual fix, per `CLAUDE.md`) - accepted deliberately, not overlooked.

## Shared error object

Every endpoint returns this same shape on failure (`api/dependencies.py`'s
`json_error()`):

```json
{
  "error": "Human-readable message",
  "code": "STABLE_ERROR_CODE"
}
```

`details` is added only for request-validation failures (a list of
field-level errors). Real codes in use today (`common/error_codes.py`):
`VALIDATION_ERROR`, `DOCUMENT_NOT_FOUND`, `RATE_LIMITED`,
`BACKEND_UNAVAILABLE`, `INDEXING_FAILED`, `QUERY_FAILED`,
`NOT_IMPLEMENTED`, `INTERNAL_ERROR`, `UNAUTHENTICATED`, `FORBIDDEN`,
`AMBIGUOUS_DOCUMENT_IDENTIFIER`. Per-file upload rejection reasons (still
inside a 200 batch response, not a top-level error): `INVALID_FILE_TYPE`,
`EMPTY_FILE`, `FILE_TOO_LARGE`, `UPLOAD_READ_FAILED`,
`SUPERSEDES_TARGET_NOT_FOUND`, `STORAGE_FAILURE`.

---

## POST /v1/genai-rag/ingest-document/documents (upload) — **Finalized**

`multipart/form-data`, two parts:
- `files` — one or more PDFs (binary, unchanged from today)
- `payload` — one JSON-string form field, parsed server-side, shape:

```json
{
  "user_profile": {
    "employee_id": "EMP051",
    "full_name": "Hana Support",
    "role": "hr_support"
  },
  "chunk_info": {
    "chunking_strategy": "recursive",
    "chunk_size": 1000,
    "chunk_overlap": 150
  },
  "document_metadata": {
    "supersedes_document_id": null,
    "doc_category": "benefits",
    "department": "HR",
    "doc_description": "401k",
    "owner": null,
    "purpose": null,
    "effective_date": null,
    "audience": null,
    "confidentiality_level": null,
    "author": null,
    "doc_date": null,
    "doc_version": null
  }
}
```

**Renamed 2026-09-25 (Phase 57), user-directed:** `doc_type` -> `doc_category`,
`doc_classification` -> `doc_description` - a pure field rename, same
meaning and same optional/nullable behavior as before, not a new field or
a semantic change.

**Added 2026-09-25 (Phase 59), user-directed:** `author`, `doc_date`,
`doc_version` - three new document-metadata fields, same
caller-overrides-extraction-guess/nullable pattern as every other field in
this sub-object. Document-level only, not chunk-level (unlike
`doc_category`/`department`/`doc_description`) - not exposed as a
Self-Query filterable field, since these describe provenance, not
something a caller would search/filter chunks by.

All fields in all three sub-objects are optional. `document_metadata`
fields the caller sends override the LLM extraction step's own guess for
that field; fields left null still get filled in by extraction as today.

`payload` itself: `max_length=20000` characters on the raw form field (same
"bound every string field" rule as the rest of this project's contracts -
generous for this shape, small enough to reject an obvious abuse case).
Missing `payload` is treated as `{}` (every field defaults). Malformed
JSON, or JSON that doesn't match the shape above, returns `422` /
`VALIDATION_ERROR` (shared error object above), same as any other
validation failure - not a 500.

Response — `200`:

```json
{
  "uploaded_count": 1,
  "duplicate_count": 0,
  "rejected_count": 0,
  "results": [
    {
      "filename": "401k-policy.pdf",
      "document_id": "d3f1...",
      "status": "uploaded",
      "uploaded_by": "EMP051",
      "chunk_info": {
        "chunking_strategy": "recursive",
        "chunk_size": 1000,
        "chunk_overlap": 150,
        "action": "insert",
        "chunks_indexed": 12,
        "chunks_removed": 0
      },
      "document_metadata": {
        "doc_category": "benefits",
        "department": "HR",
        "doc_description": "401k",
        "owner": null,
        "purpose": null,
        "effective_date": null,
        "audience": null,
        "confidentiality_level": null,
        "author": null,
        "doc_date": null,
        "doc_version": null
      },
      "versioning_info": {
        "document_version": 1,
        "is_current": true,
        "supersedes": null,
        "superseded_by": null
      },
      "error": null,
      "error_code": null,
      "message": null,
      "file_size_bytes": 123456
    }
  ]
}
```

`status` is `"uploaded"`, `"duplicate"`, or `"rejected"` per file - a bad
file in a batch doesn't fail the good ones (unchanged from today).

---

## POST /v1/genai-rag/retrieve-document/query — Finalized

Same `payload`-as-JSON-string-in-multipart pattern doesn't apply here -
this endpoint has no file, so it can be a real JSON body, no wrapper trick
needed.

```json
{
  "user_profile": {
    "employee_id": "EMP051",
    "full_name": "Hana Support",
    "role": "hr_support"
  },
  "query": "How many weeks of paid parental leave does JPMorgan Chase provide?",
  "search_options": {
    "top_k": 5,
    "vector_db": "chromadb",
    "search_strategy": "similarity",
    "use_multi_query": false,
    "use_self_query": false,
    "llm_provider": "openai"
  },
  "generation_options": {
    "model_name": "gpt-4.1-mini",
    "temperature": 0.0,
    "max_tokens": 500
  },
  "enable_conversation_memory": false,
  "conversation_id": null
}
```

**Added 2026-09-25 (Phase 58), user-directed:** `enable_conversation_memory`
(bool, default `false`) and `conversation_id` (string, default `null`).
When `enable_conversation_memory` is `true`: if `conversation_id` is
omitted/null, a new one is generated server-side and returned in the
response - pass that same value back on the next call to continue the
conversation. Server-side, in-memory store (see Phase 58 entry) - lost on
restart, single-process only; a cache DB is planned later, not built now.
When `false` (the default), behavior is unchanged from before this phase -
every query is independent, `conversation_id` in the response is `null`.

Response:

```json
{
  "query": "How many weeks of paid parental leave does JPMorgan Chase provide?",
  "answer_info": {
    "answer": "...",
    "model_used": "gpt-4.1-mini"
  },
  "retrieval_info": {
    "vector_db": "chromadb",
    "search_strategy": "similarity",
    "applied_filter": null,
    "sources": [
      { "document_id": "d3f1...", "filename": "401k-policy.pdf", "chunk_index": 3, "text": "...", "score": 0.87 }
    ]
  },
  "conversation_id": null
}
```

## POST /v1/single-agentic-rag/query — Finalized (Phase 55)

Same identity-in-payload pattern as `genai-rag`'s query endpoint. No
`search_options`/`generation_options` - the agent decides retrieval/tool
choice itself, there's nothing for the caller to override yet.

```json
{
  "user_profile": {
    "employee_id": "EMP052",
    "full_name": "Eddy Employee",
    "role": "employee"
  },
  "query": "What is my PTO balance?",
  "max_iterations": 5,
  "enable_conversation_memory": false,
  "conversation_id": null
}
```

**Added 2026-09-25 (Phase 58):** same `enable_conversation_memory`/
`conversation_id` contract as `genai-rag`'s query endpoint above - same
server-side, in-memory store, shared module. Only the final answer per
turn is saved to history here, not the intermediate tool calls within a
turn's own reasoning loop.

Response:

```json
{
  "query": "What is my PTO balance?",
  "answer": "Your current Paid Time Off (PTO) balance is 11 days available.",
  "tools_used": [
    { "tool_name": "GetLeaveBalance", "tool_input": "" }
  ],
  "iterations": 2,
  "conversation_id": null
}
```

`tools_used` is empty when the agent answers without calling anything
(e.g. a greeting). No `sources`/`retrieval_info` shape like `genai-rag`'s
response - a tool-calling agent's grounding varies per tool, not always a
vector-store chunk list, so it isn't forced into that shape here.

## POST /v1/multi-agentic-rag/query — Finalized (Phase 61, scaffold only)

Same identity-in-payload/RBAC/rate-limiting pattern as every other query
endpoint. **The pipeline itself is stubbed** (Phase 61) - this contract is
real and finalized, but a well-formed request returns `501` today, naming
`ai/agents/workflow_agents/multi_agent_pipeline.py`. Real orchestration
logic is a follow-up phase, not built yet.

```json
{
  "user_profile": {
    "employee_id": "EMP052",
    "full_name": "Eddy Employee",
    "role": "employee"
  },
  "query": "Plan my next 2 weeks: check my PTO balance and summarize the parental leave policy",
  "enable_conversation_memory": false,
  "conversation_id": null
}
```

No `max_iterations` at the top level - each dispatched sub-agent will
have its own, once orchestration exists; not a caller-facing knob yet.

Response (once implemented):

```json
{
  "query": "Plan my next 2 weeks: check my PTO balance and summarize the parental leave policy",
  "answer": "...",
  "tasks": [
    { "agent": "domain_agent_name", "focus": "what this sub-agent was asked to do" }
  ],
  "tools_used": [
    { "tool_name": "GetLeaveBalance", "tool_input": "" }
  ],
  "iterations": 3,
  "conversation_id": null
}
```

`tasks` records which sub-agent(s) the router dispatched to and why -
`AgentTaskInfo` in `models/multi_agentic_rag.py`. `tools_used` reuses
`ToolCallInfo` from `models/agentic_rag.py` (single-agentic-rag's own
shape) - aggregated across every sub-agent's own tool calls, not
per-agent, matching `single-agentic-rag`'s existing flat shape rather
than inventing a nested one.

## GET /v1/genai-rag/ingest-document/documents, GET .../{id} — Finalized

Identity: query params (`?employee_id=...&full_name=...&role=...`), not a
body - see the Phase 96 revision note above; a real browser can't send a
body on `GET` at all. `{id}` stays in the path for the single-document
form. Response is where the same 27-flat-field problem
from `DocumentRecord` (flagged earlier this session) actually lives -
reuses the same three sub-objects as the upload response, not redefined:

```json
{
  "id": "d3f1...",
  "filename": "401k-policy.pdf",
  "file_path": "data/uploads/d3f1.../401k-policy.pdf",
  "status": "indexed",
  "error_message": null,
  "created_at": "2026-09-19T...",
  "updated_at": "2026-09-19T...",
  "last_indexed_at": "2026-09-19T...",
  "chunk_ids": ["d3f1...:0", "d3f1...:1"],
  "chunk_count": 2,
  "file_size_bytes": 123456,
  "embedding_model": "text-embedding-3-small",
  "embedding_dimension": 1536,
  "uploaded_by": "EMP051",
  "chunk_info": { "chunk_size": 1000, "chunk_overlap": 150 },
  "document_metadata": { "doc_category": "benefits", "department": "HR", "doc_description": "401k", "owner": null, "purpose": null, "effective_date": null, "audience": null, "confidentiality_level": null, "author": null, "doc_date": null, "doc_version": null },
  "versioning_info": { "document_version": 1, "is_current": true, "supersedes": null, "superseded_by": null }
}
```
`GET /documents` (list) wraps this in `{"count": N, "documents": [...]}`, unchanged.

## DELETE /v1/genai-rag/ingest-document/documents/{id}, DELETE .../documents (all) — Finalized

Body: `{"user_profile": {...}}` only, same as the GET endpoints above.
This is the endpoint the audit trail matters most for - `deleted_by` on
the response, using the caller's `employee_id`:

```json
{ "document_id": "d3f1...", "filename": "401k-policy.pdf", "chunks_removed": 12, "deleted_by": "EMP051" }
```
```json
{ "documents_deleted": 6, "chunks_removed": 54, "deleted_by": "EMP051" }
```

## GET .../documents/cleanup/preview, DELETE .../documents/cleanup — Finalized (Phase 46)

`GET .../preview`: query params, per the Phase 96 revision above.
`DELETE .../cleanup`: body, `{"user_profile": {...}}` only, unchanged.
Registered before `GET/DELETE /documents/{id}` so `cleanup` is
never read as a document id. "Test noise" = `file_size_bytes` below
`TEST_NOISE_MAX_FILE_SIZE_BYTES` (`.env`, default `1024`) - a structural
signal (every test-generated file is a short fake string), not a guess.

Preview (`GET`) - deletes nothing:
```json
{
  "count": 2,
  "threshold_bytes": 1024,
  "documents": [
    { "id": "a1b2...", "filename": "noise.pdf", "file_size_bytes": 42, "created_at": "2026-09-20T..." }
  ]
}
```

Delete (`DELETE`) - same response shape as delete-all:
```json
{ "documents_deleted": 2, "chunks_removed": 0, "deleted_by": "EMP051" }
```

## GET /health, GET /ping — Finalized: no identity, no change

No identity params, on purpose - both are called by automated
infrastructure (Docker's `HEALTHCHECK`, CI's deploy smoke test), not by an
employee acting on data. Requiring `employee_id`/`role` here would break
those automated callers, which have no employee context to send. Audit
trail is for actions on documents (upload/query/delete) - these two don't
touch documents. Response is already grouped by backend
(`checks.llm`/`checks.vector_database`/`checks.metadata_database`) -
no change needed there either, it already matches this exercise's pattern:

```json
{ "status": "healthy", "app": "HRB Chatbot", "checks": { "llm": {...}, "vector_database": {...}, "metadata_database": {...} } }
```
`/ping`: `{"status": "ok"}`, unchanged - it's deliberately minimal (no provider calls).

## POST /v1/genai-rag/ingest-document/documents/presigned-upload — Finalized (Phase 89)

**Additive, confirmed with the user 2026-10-06 - does not replace, and
nothing changes about, the existing `POST .../documents` above.** Single
file only, no batch variant this phase.

Request, JSON (not multipart - no file bytes exist yet):
```json
{
  "user_profile": { "employee_id": "EMP051", "full_name": "Hana Support", "role": "hr_support" },
  "filename": "401k-policy.pdf",
  "content_type": "application/pdf",
  "chunk_info": { "chunking_strategy": null, "chunk_size": null, "chunk_overlap": null },
  "document_metadata": {
    "supersedes_document_id": null, "doc_category": "benefits", "department": "HR",
    "doc_description": "401k", "owner": null, "purpose": null, "effective_date": null,
    "audience": null, "confidentiality_level": null, "author": null, "doc_date": null, "doc_version": null
  }
}
```
`chunk_info`/`document_metadata` are the exact same sub-objects the
synchronous endpoint above already accepts - identical fields, identical
optional/nullable behavior. Validated the same way the synchronous
endpoint validates a file: content-type/extension check
(`error_codes.INVALID_FILE_TYPE`), `supersedes_document_id` must
reference a real document if given (`error_codes.
SUPERSEDES_TARGET_NOT_FOUND`). Role gate and rate limit unchanged from
every other mutating route (`hr_support` only).

Response — `200`:
```json
{ "document_id": "d3f1...", "upload_url": "https://hrb-chatbot-kb-uploads.s3.amazonaws.com/...", "expires_in_seconds": 300, "status": "pending_upload" }
```
A **new, separate response shape** - not `DocumentUploadResponse` above -
since nothing has been chunked/embedded/indexed yet when this responds.
The client `PUT`s the file body directly to `upload_url` (plain HTTP, no
AWS SDK, no credentials needed client-side - see `docs/dev-reference/
deployment-guide/05-rag-ingestion-batch.html`'s "Presigned URLs" section),
then polls the existing `GET /v1/genai-rag/ingest-document/documents/{id}`
above for the real indexing result once Phase 88's S3 → SQS → Lambda
pipeline picks it up - same response shape that endpoint already returns
today, no change there either.
