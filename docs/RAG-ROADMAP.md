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

Updated 2026-09-07. This table is the fast-read summary; the full "Phases"
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
| 5 — Query endpoint, stubbed | Claude Code | ✅ Done |
| 5.1 — Query decomposition | Hand-written | 📋 Planned |
| 5.2 — Query variants | Hand-written | 📋 Planned |
| 5.3 — Prompt chaining + versioning | Hand-written | 📋 Planned |
| 6 — Retrieval + grounded generation, COT | Hand-written | 📋 Planned |
| 6.1 — Contracts/validation for query path | Claude Code | 📋 Planned (gated on Phase 6) |
| 7 — Guardrails (input + output) | Hand-written | 📋 Planned |
| 8 — Golden dataset + evaluations + A/B | Hand-written | 📋 Planned |
| 9 — Bedrock as an LLM provider | Claude Code | ✅ Done |
| 10 — Docker + AWS deployment (App Runner) | Claude Code | 🚧 **In progress** - App Runner service created, still `OPERATION_IN_PROGRESS` as of last check; Postgres/Neon leg pending the user's Neon signup |
| 11 — CI/CD + GitHub | Claude Code | 📋 Planned (unblocked - repo/branch/push already done) |

**If you're picking this up after a restart with no session memory**, the
one thing to check first is Phase 10's actual live AWS state - it does not
show up by reading code, only by querying AWS directly:
```
aws apprunner describe-service --region us-east-1 \
  --service-arn arn:aws:apprunner:us-east-1:418884736369:service/hrb-chatbot/63fcfce613a5425ab43cf8fd8dad8228
```
(needs `aws-cli` ≥ 2.something-with-apprunner, or run the equivalent
`boto3` call - see Phase 10 below for why the CLI here may still be too old).

## Phases

- [x] **Phase 1 (Claude Code) — ChromaDB client + gateway.**
  `common/clients/db_client/chroma_client.py`, `db_gateway.py`.
  `health_checks.py`'s `check_vector_database()` wired into `check_everything()`.
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

  Verified live: a valid query → `501` naming
  `ai/pre_processing/query_decompose.py` and Phase 5.1 specifically (not a
  generic error); empty `query` → `422` (min length); `top_k=100` → `422`
  (max 20) - both caught by the contract before a handler ever runs, not
  downstream. Confirmed no regression on `/health`, `/docs`, or the
  existing `/rag/documents` endpoints.
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
- [ ] **Phase 6 (hand-written) — Retrieval + grounded generation, with COT.**
  `ai/rag_pipeline/query_retrieval/`, `ai/rag_pipeline/response_generation/`.
  Workshop Module 4 (anti-hallucination/grounding). Chain-of-thought
  prompting is part of this phase, not separate.
- [ ] **Phase 6.1 (Claude Code) — Contracts/validation/logging for the query
  path.** Same standard already applied to upload/indexing (typed
  request/response, `json_error()` shape, try/except with logging) -
  extended to cover the LLM response-generation call and the vector-store
  query call specifically, per explicit instruction.
- [ ] **Phase 7 (hand-written) — Guardrails, both directions.**
  `ai/pre_processing/guardrails_input.py` (currently empty) - a validation
  gateway for the incoming query before it reaches retrieval.
  `ai/rag_pipeline/response_generation/guardrails_output/` (currently
  empty) - validates/filters the generated answer before it's returned.
- [ ] **Phase 8 (hand-written) — Golden dataset + A/B testing + evaluations.**
  `ai/rag_pipeline/evaluations/` (currently empty). Workshop Module 5
  (retrieval metrics: Precision@K/Recall@K/F1; generation metrics:
  groundedness/completeness via LLM-as-judge). The golden dataset (a fixed
  set of question → expected-answer/expected-source pairs) is what both
  the evaluation metrics and any A/B comparison between prompt/chunking
  configurations run against.
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
- [ ] **Phase 10 (Claude Code, in progress) — Docker + AWS deployment via App Runner.**
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
  | App Runner service | `arn:aws:apprunner:us-east-1:418884736369:service/hrb-chatbot/63fcfce613a5425ab43cf8fd8dad8228` → `https://hr5nbczbdp.us-east-1.awsapprunner.com` |

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

  **What's actually done as of this writing:**
  - [x] ECR repo created, image built locally and pushed as `:latest`.
  - [x] Both IAM roles created with scoped (non-admin) policies.
  - [x] Five secrets created in Secrets Manager from `.env`'s current keys.
  - [x] `RAG_METADATA_STORE` switch added and wired through all three call sites.
  - [x] App Runner service created (`create_service` call succeeded).
  - [ ] **App Runner service status was still `OPERATION_IN_PROGRESS`
    (first deploy - image pull + provisioning) the last time it was
    checked - not yet confirmed `RUNNING` or health-checked. If a fresh
    session picks this up, the very first thing to do is
    `describe_service` on the ARN above (or check the URL directly) before
    assuming anything about this deployment's state.**

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

  **Stalled, not resolved:** upgrading the AWS CLI (`winget upgrade --id
  Amazon.AWSCLI`) was started and got stuck at "Starting package install..."
  for several minutes with no further output - almost certainly waiting on
  a UAC elevation prompt this non-interactive shell can never answer. Does
  not block anything above (deployment used `boto3` throughout), but the
  CLI itself is still `2.0.30` as of this writing. If this matters later,
  it needs a human to run the MSI installer directly and click through UAC
  - not something to keep retrying the same way from here.

  **Not yet done:** CloudWatch log group verification (App Runner creates
  one automatically per service - not yet confirmed it's receiving this
  app's `structlog`/`loguru` output correctly), a custom domain (not
  requested), and any autoscaling configuration beyond App Runner's default.
- [ ] **Phase 11 (Claude Code, unblocked) — CI/CD + GitHub.** No longer
  blocked: `hrb_chatbot_v2` is a git repository with remote
  `https://github.com/rvsree/hrb_chatbot_v2.git`, branch `hrb_rag_pipelines`
  created before the first commit and pushed (`5798a7b`, 118 files). Remote
  `main` is still empty - nothing merged there yet. GitHub Actions workflow
  and git hooks not yet started.

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

## Verification checklist (Phases 1-3)

1. `GET /health?deep=true` → vector + metadata database checks healthy. **Done.**
2. `POST /rag/documents` with a real PDF from `resources/kb_docs/` → 200,
   document id returned, file in `data/uploads/`, SQLite row exists. **Done**,
   including the batch partial-success case.
3. `POST /rag/documents/{id}/index` → clear `NotImplementedError` naming
   `ai/doc_processing/`, not a crash.
4. `POST /rag/query` → same stubbed-but-clear behavior, naming
   `ai/rag_pipeline/`.
