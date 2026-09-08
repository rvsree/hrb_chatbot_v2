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

`/health` currently reports two checks: `llm` (whichever provider you asked
for, `openai` by default) and `database` (ChromaDB). **Tavily has a client
(`common/clients/web_client/tavily_client.py`) but is not wired into
`/health` yet** - a known gap, tracked in
[docs/BACKLOG.md](docs/BACKLOG.md), not something broken.

### Upload documents / ask the knowledge base

Not implemented yet. `POST /rag/documents` and `POST /rag/query` land in
Phases 2-6 of [docs/RAG-ROADMAP.md](docs/RAG-ROADMAP.md). This section gets
filled in with real examples once those endpoints exist - don't expect
anything at those paths yet.

## Running in a container

```powershell
docker build -t hrb-chatbot:local .
docker run --rm --env-file .env -p 8093:8093 hrb-chatbot:local
```

**This Dockerfile has not been build-tested** - Docker Desktop wasn't running
in the environment it was written in, so this is a mirror of a proven pattern
from a sibling project, not something confirmed working end to end yet.
Verify it builds and the container passes its `HEALTHCHECK` before relying on
it.

## Dependencies

`requirements.txt` pins exact versions (`==`) deliberately, not loose ranges
- `chromadb`'s Python-version fragility (see Prerequisites) and the fact that
a Dockerfile now exists are both reasons a silent version drift is worse than
a pin that occasionally needs a deliberate bump.

## Project conventions

See [docs/CODING-STANDARDS.md](docs/CODING-STANDARDS.md) for the error
handling, logging, and API contract conventions this codebase follows.

## Known gaps and planned work

See [docs/BACKLOG.md](docs/BACKLOG.md).
