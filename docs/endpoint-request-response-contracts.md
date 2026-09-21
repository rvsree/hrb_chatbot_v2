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

- `GET /v1/genai-rag/ingest-document/documents`, `GET .../{id}`,
  `DELETE .../{id}`, `DELETE .../documents` (all): body is
  `{"user_profile": {...}}` only - no other fields.
- `POST` endpoints (upload, query): `user_profile` is one sub-object
  alongside the endpoint's other fields, same as already documented below.
- `GET /health`/`GET /ping` stay exactly as they are - no identity, no
  RBAC. Confirmed: they're called by automated infrastructure (Docker
  `HEALTHCHECK`, CI smoke test), not an employee acting on data.

**Known, accepted tradeoff, on record per the 2026-09-20 security review:**
`role` now comes from the same payload/query-params as the action it
gates, so `check_role()` can't stop anyone who knows the field name - RBAC
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
    "employee_id": "E00001",
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
    "doc_type": "benefits",
    "department": "HR",
    "doc_classification": "401k",
    "owner": null,
    "purpose": null,
    "effective_date": null,
    "audience": null,
    "confidentiality_level": null
  }
}
```

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
      "uploaded_by": "E00001",
      "chunk_info": {
        "chunking_strategy": "recursive",
        "chunk_size": 1000,
        "chunk_overlap": 150,
        "action": "insert",
        "chunks_indexed": 12,
        "chunks_removed": 0
      },
      "document_metadata": {
        "doc_type": "benefits",
        "department": "HR",
        "doc_classification": "401k",
        "owner": null,
        "purpose": null,
        "effective_date": null,
        "audience": null,
        "confidentiality_level": null
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
    "employee_id": "E00001",
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
  }
}
```

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
  }
}
```

## GET /v1/genai-rag/ingest-document/documents, GET .../{id} — Finalized

Body: `{"user_profile": {...}}` only, alongside `{id}` in the path for the
single-document form. Response is where the same 27-flat-field problem
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
  "uploaded_by": "E00001",
  "chunk_info": { "chunk_size": 1000, "chunk_overlap": 150 },
  "document_metadata": { "doc_type": "benefits", "department": "HR", "doc_classification": "401k", "owner": null, "purpose": null, "effective_date": null, "audience": null, "confidentiality_level": null },
  "versioning_info": { "document_version": 1, "is_current": true, "supersedes": null, "superseded_by": null }
}
```
`GET /documents` (list) wraps this in `{"count": N, "documents": [...]}`, unchanged.

## DELETE /v1/genai-rag/ingest-document/documents/{id}, DELETE .../documents (all) — Finalized

Body: `{"user_profile": {...}}` only, same as the GET endpoints above.
This is the endpoint the audit trail matters most for - `deleted_by` on
the response, using the caller's `employee_id`:

```json
{ "document_id": "d3f1...", "filename": "401k-policy.pdf", "chunks_removed": 12, "deleted_by": "E00001" }
```
```json
{ "documents_deleted": 6, "chunks_removed": 54, "deleted_by": "E00001" }
```

## GET .../documents/cleanup/preview, DELETE .../documents/cleanup — Finalized (Phase 46)

Body: `{"user_profile": {...}}` only, same pattern as the rest of this
section. Registered before `GET/DELETE /documents/{id}` so `cleanup` is
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
{ "documents_deleted": 2, "chunks_removed": 0, "deleted_by": "E00001" }
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
