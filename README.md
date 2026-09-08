# HRB Chatbot v2

An HR benefits chatbot backed by a RAG pipeline over the JPMC benefits
knowledge base (`resources/kb_docs/`). Being built by hand, one feature at a
time, to apply RAG concepts from the Interview Kickstart FDE cohort - see
[docs/RAG-ROADMAP.md](docs/RAG-ROADMAP.md) for the phase-by-phase plan and
current status (that file is the source of truth for "what's done" - this
README doesn't repeat it).

## Prerequisites

- **Python 3.12** - not 3.13/3.14. `chromadb` depends on Pydantic v1
  internals that Python 3.13 removed.
- An **OpenAI API key** at minimum (`OPENAI_API_KEY` in `.env`). Anthropic
  and OpenRouter keys are optional - the app runs fully on OpenAI alone.

## 1. Running locally, from a terminal

The venv already exists at `.venv/`. From the repository root:

```powershell
# install (only needed after requirements.txt changes)
.venv\Scripts\python.exe -m pip install -r requirements.txt

# run
.venv\Scripts\python.exe -m uvicorn src.hrb_chatbot.main:app --reload --port 8093
```

Confirm it came up:

```powershell
curl http://127.0.0.1:8093/health
```

`200` with `"status":"healthy"` means it's ready. `/docs` gives the
interactive Swagger UI.

Note the import root: everything is written as `from src.hrb_chatbot....`,
not `from hrb_chatbot....` - `src/__init__.py` exists on purpose, and the app
is always run as a module from the repository root, never from inside `src/`.

## 2. IntelliJ IDEA / PyCharm - run & debug configurations

Needs the **Python** plugin (Community edition has it; PyCharm ships with it
built in).

### Setup - once per machine

1. **Point the project at the venv.** *File → Project Structure → SDKs → +
   → Add Python SDK → Existing environment*, then choose
   `...\hrb_chatbot_v2\.venv\Scripts\python.exe`. Assign that SDK to the
   module.
2. **Mark the repository root as the Sources Root** (not `src/`). Right-click
   the repo root → *Mark Directory as → Sources Root*. This is what makes
   `from src.hrb_chatbot...` resolve - marking `src/` itself instead makes
   every import underline red even though the code runs fine from a terminal.

### Run configuration - "hrb-chatbot-server"

*Run → Edit Configurations → + → Python*:

| Field | Value |
|---|---|
| Name | `hrb-chatbot-server` |
| Run target | `Module name` (switch the radio from *Script path*) |
| Module name | `uvicorn` |
| Parameters | `src.hrb_chatbot.main:app --reload --port 8093` |
| Working directory | the repository root |
| Python interpreter | the project SDK (`.venv`) |
| Environment variables | *(leave empty - `.env` is loaded by the app itself)* |

### Debug configuration - "hrb-chatbot-debug"

Duplicate the run configuration above and **delete `--reload`**. That's the
only difference - `--reload` runs the app in a child process, which breaks
an attached debugger.

## 3. Testing the endpoints

### Health - every backend service currently wired up

```powershell
# shallow - instant, no network, no cost
curl http://127.0.0.1:8093/health

# deep - one real but free call per service (no chat completion, no tokens spent)
curl "http://127.0.0.1:8093/health?deep=true"

# check a specific LLM provider
curl "http://127.0.0.1:8093/health?deep=true&provider=anthropic"
curl "http://127.0.0.1:8093/health?deep=true&provider=openrouter"
```

`/health` reports three checks - `llm` (whichever provider you asked for,
`openai` by default), `vector_database` (`chromadb` by default, pass
`vector_provider=pinecone` to check the other), and `metadata_database`
(`sqlite` by default, pass `metadata_provider=postgres` to check the
other). **Tavily has a client
(`common/clients/web_client/tavily_client.py`) but is not wired into
`/health` yet** - a known gap, tracked in
[docs/BACKLOG.md](docs/BACKLOG.md), not something broken.

### Upload documents, index them, and ask the knowledge base

All of these are implemented and verified live (see
[README_TEST.md](README_TEST.md) for every case, happy path and edge case,
run against a real server):

```powershell
# upload a real PDF - copy the document_id from the response
curl -F "files=@resources/kb_docs/JPMC Healthcare Benefits.pdf;type=application/pdf" http://127.0.0.1:8093/v1/rag/documents

# index it (spends: one real embedding call per chunk)
curl -X POST http://127.0.0.1:8093/v1/rag/documents/<document_id>/index

# ask a question - the query endpoint itself works, but the underlying
# retrieval/generation pipeline (Phase 6) is hand-written and not built yet,
# so this returns 501 naming ai/rag_pipeline/pipeline.py until it lands
curl -X POST http://127.0.0.1:8093/v1/rag/query -H "Content-Type: application/json" -d "{\"query\": \"How many weeks of parental leave do I get?\"}"
```

For testing every endpoint from a GUI instead of curl, import
[postman/hrb_chatbot.postman_collection.json](postman/hrb_chatbot.postman_collection.json)
into Postman - it covers the same happy-path and edge cases as
README_TEST.md, ready to run against `{{base_url}}` (local or the deployed
App Runner URL). Once Phase 6 exists,
[resources/golden_dataset/golden_dataset.json](resources/golden_dataset/golden_dataset.json)
has 22 real question/expected-answer pairs grounded in the actual
`resources/kb_docs/` PDFs, for evaluating whether real answers are grounded
and correct rather than hallucinated.

## Running in a container

```powershell
docker buildx build --provenance=false --sbom=false --output type=docker -t hrb-chatbot:local .
docker run --rm --env-file .env -p 8093:8093 hrb-chatbot:local
```

Build- and run-verified, including a real deployment to AWS App Runner -
see [docs/AWS-DEVOPS-RUNBOOK.md](docs/AWS-DEVOPS-RUNBOOK.md) for the full
containerize → ECR → App Runner pipeline, exactly which build flags are
required and why (three separate real bugs were found and fixed getting
this image to actually run in App Runner, not just build locally), and how
to review/validate every AWS resource this project provisions.

## Branching and CI/CD

`feature-<name>` branches → `develop` (integration, fully gated) →
`master` (production - `deploy.yml` deploys from here only). See
[docs/CICD-BRANCHING-STRATEGY.md](docs/CICD-BRANCHING-STRATEGY.md) for the
branch roles, every CI gate and the threshold it enforces (test pass rate,
coverage floor, security scanning, and the A/B-testing bar for once
Phase 8's eval harness exists), and the deployment-testing step that now
runs after every real deploy.

## Running the tests

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # once
.venv\Scripts\python.exe -m pytest -v
```

No test needs a real API key or network call - see
[docs/TESTING-GUIDE.md](docs/TESTING-GUIDE.md) for what's covered, why
those specific cases, and the fake-based pattern to copy when testing the
hand-written RAG pipeline once it exists.

## Dependencies

`requirements.txt` pins exact versions (`==`) deliberately, not loose ranges
- `chromadb`'s Python-version fragility (see Prerequisites) and the fact that
a Dockerfile now exists are both reasons a silent version drift is worse than
a pin that occasionally needs a deliberate bump. `requirements-dev.txt` is
test-only dependencies, kept separate so a production image never installs
them.

## Project conventions

See [docs/CODING-STANDARDS.md](docs/CODING-STANDARDS.md) for the error
handling, logging, and API contract conventions this codebase follows.

## Known gaps and planned work

See [docs/BACKLOG.md](docs/BACKLOG.md).

## Design questions and FAQ

[docs/FAQ.md](docs/FAQ.md) - deep-dive answers on document update
strategy, where RAG metadata lives and which store is right for filtering
search results, and how document indexing/categorization works - each
split clearly into what this project does today vs. general RAG design
reasoning, written for both gap-finding and interview prep.
