# Hand-off - start here

Written 2026-09-08, at the end of a session, because the user's laptop is
about to restart and this conversation's memory will be gone. If you are
a fresh agent (or the user, in a new session) picking this project back
up with zero context, **read this file first, before any other doc** -
it's the orientation layer; everything else in `docs/` is the depth layer
it points into.

## Update, 2026-09-08 - branches created

Four branches now exist on GitHub, all cut from `hrb_rag_pipelines` at commit
`416f977` (same code on each, no divergence yet):

| Branch | Intent |
|---|---|
| `main` | Production/deploy branch - `deploy.yml` triggers on push here |
| `developer` | Integration branch - feature branches merge here before `main` |
| `feature` | Generic feature-branch parent |
| `feature-kb-indexing-rag-pipeline` | This session's working branch - carries this doc's own update plus whatever lands next |

**`hrb_rag_pipelines` (the original branch) still exists too** - it was not
deleted, just no longer the only branch. Treat it as superseded by `main`/
`developer` going forward rather than continuing to commit to it directly.

**Pushing `main` for the first time did not deploy anything** - creating the
branch was a `git push`, not a merge with new commits, and even if it had
triggered `deploy.yml`, that workflow would fail today: the two GitHub
Actions secrets (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) still haven't
been added (see [Blocked on the user](#blocked-on-the-user---three-concrete-items)
below - that item is unchanged by this update, still open).

Going forward, the natural flow is: work happens on a `feature-*` branch →
PR into `developer` → PR into `main` when ready to actually deploy. Nothing
in CI enforces this yet (no branch protection rules were set up - that's a
GitHub repo-settings action, not something done from here).

## TL;DR

This is a hand-built HR benefits RAG chatbot (JPMC benefits PDFs → chunk →
embed → index → retrieve → answer), built by the user personally to learn
RAG concepts from an Interview Kickstart FDE cohort. **Claude Code builds
boilerplate and infrastructure; the user hand-writes the actual RAG logic**
(chunking strategy, retrieval, generation, evaluation) - this split is the
single most important thing to not violate, see
[Division of labor](#division-of-labor---read-before-touching-anything-under-ai). Twelve
phases are done (upload, index, deploy to real AWS, CI/CD, a full REST API
hardening pass). The core RAG query pipeline itself
(`ai/rag_pipeline/pipeline.py`) is **still an intentional stub** -
`POST /v1/rag/query` returns 501 by design, not by accident, until the
user builds Phase 6 by hand.

## Current status snapshot

| Area | Status |
|---|---|
| Local dev (upload, index, health) | ✅ Working, verified live |
| Deployed to AWS App Runner | ✅ `RUNNING` - confirmed again right before this handoff was written (real `200` from `GET /health`) |
| RAG query (retrieval + generation) | ❌ Stub only - `501`, by design, Phase 6 is the user's hand-written work |
| CI (GitHub Actions) | ✅ Green - 35 tests, verified passing on GitHub itself, not just locally |
| CD (GitHub Actions → App Runner) | 🚧 Written, never actually triggered - see [Blocked on the user](#blocked-on-the-user---three-concrete-items) |
| Golden dataset | ✅ Done (22 cases, real facts from the real PDFs) - a one-time Claude-Code override of the hand-written boundary, same as chunking/embedding/indexing was |
| REST API hardening (versioning, idempotency, rate limiting, error handling) | ✅ Done, this session |
| Test suite | ✅ 35 tests, all passing, no test needs a key or network call |

Full phase-by-phase detail: [`docs/RAG-ROADMAP.md`](RAG-ROADMAP.md)'s
"Status at a glance" table - this snapshot is a summary of that summary;
if the two ever disagree, RAG-ROADMAP.md is the authority, not this file
(this file isn't kept live-updated the way that one is meant to be).

## Blocked on the user - three concrete items

Nothing here blocks continuing local development. These only block the
*deployment* pipeline going further:

1. **Neon Postgres signup** (free, at neon.tech) - `.env` still has
   `POSTGRES_DB_HOST=localhost` (confirmed right before writing this
   handoff), meaning the deployed App Runner service still runs
   `RAG_METADATA_STORE=sqlite` (ephemeral - wiped on every redeploy) as a
   documented, temporary compromise. Once Neon exists: create 5 secrets
   in AWS Secrets Manager (`hrb-chatbot/POSTGRES_DB_HOST/PORT/NAME/USER/PASSWORD`),
   flip `RAG_METADATA_STORE` to `postgres` via `apprunner update-service` -
   config-only, no rebuild. Full steps in
   [`docs/AWS-DEVOPS-RUNBOOK.md`](AWS-DEVOPS-RUNBOOK.md).
2. **Two GitHub Actions secrets never confirmed added** -
   `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` for the
   `hrb-chatbot-github-actions-deploy` IAM user, needed for `deploy.yml`.
   **A real, live AWS access key is still sitting in plaintext** at
   `C:\Users\sreed\AppData\Local\Temp\claude\...\scratchpad\github_actions_credentials.txt`
   on this machine - confirmed still present right before this handoff was
   written. Either copy it into GitHub (Settings → Secrets and variables →
   Actions) and delete the file, or delete the file and rotate the key if
   it's no longer wanted - don't leave it sitting there indefinitely.
3. ~~`main` branch doesn't exist on GitHub at all yet~~ **Resolved
   2026-09-08** - `main`, `developer`, `feature`, and
   `feature-kb-indexing-rag-pipeline` all now exist on GitHub, see
   [Update, 2026-09-08](#update-2026-09-08---branches-created) above.
   `deploy.yml` still hasn't actually run a real deploy though - the branch
   was created with a plain `git push`, and the next push to `main` that
   *would* trigger it will fail until item 2 above (the GitHub secrets) is
   done.

None of these are code problems - they're real-world account actions only
the user can do (an email signup, pasting a value into GitHub's own UI,
deciding when to merge).

## Division of labor - read before touching anything under `ai/`

This is the rule most likely to be violated by a fresh agent who hasn't
internalized it:

| Layer | Owner | Where |
|---|---|---|
| FastAPI routes, request/response models, infra (rate limiting, idempotency, versioning) | **Claude Code** | `api/`, `models/`, `common/` |
| Client/gateway layer (LLM providers, vector stores, metadata stores) | **Claude Code** | `common/clients/` |
| Chunking, embedding, indexing | Claude Code, **but only because of an explicit one-time override** the user granted (matches the golden dataset's own override) | `ai/doc_processing/` |
| Retrieval, generation, query decomposition, guardrails, evaluations | **Hand-written by the user** - still stubs, `NotImplementedError` on purpose | `ai/rag_pipeline/`, `ai/pre_processing/` |

**Do not implement `ai/rag_pipeline/pipeline.py`'s real logic (or
`ai/pre_processing/`) without the user explicitly asking again the same
way they asked for the chunking/embedding/indexing override** - that's
the whole point of this project for them. If asked to "move the project
forward" without qualification, the correct read is: continue
Claude-Code-owned infrastructure work, or ask which specific hand-written
phase (5.1-8 in RAG-ROADMAP.md) they want to do together, not silently
write their RAG logic for them.

## Doc map - where to find depth

Don't re-derive any of this from the code - it's already written down:

| Doc | What's in it |
|---|---|
| [`RAG-ROADMAP.md`](RAG-ROADMAP.md) | **The source of truth.** Full phase-by-phase history, every real bug found and fixed, exact reasoning behind every architectural decision. Start here for "what happened and why." |
| [`BACKLOG.md`](BACKLOG.md) | Known gaps, explicitly not blocking, with resolved items struck through rather than deleted |
| [`FAQ.md`](FAQ.md) | Deep-dive Q&A - document update strategy, metadata storage, indexing/categorization, performance, evaluation metrics (Precision@K/Recall@K/F1), golden datasets, A/B testing, and REST API contract-first design (versioning/idempotency/rate limiting/error handling) - written for interview prep as much as for this project |
| [`TESTING-GUIDE.md`](TESTING-GUIDE.md) | What's tested, why those cases, the fake-based pattern to copy for the hand-written pipeline |
| [`AWS-DEVOPS-RUNBOOK.md`](AWS-DEVOPS-RUNBOOK.md) | The full local→container→ECR→App Runner pipeline, every AWS resource and how to validate it, the manual git workflow, and three real deployment bugs documented in enough detail to never rediscover them the hard way |
| [`S3-ASYNC-UPLOAD-DESIGN.md`](S3-ASYNC-UPLOAD-DESIGN.md) | Design-only, not implemented - a future event-driven ingestion architecture |
| [`CODING-STANDARDS.md`](CODING-STANDARDS.md) | Error handling, logging, API contract conventions |
| [`README.md`](../README.md) / [`README_TEST.md`](../README_TEST.md) | How to run it locally, and a verified-live test case for every endpoint (happy + edge) |
| `resources/golden_dataset/golden_dataset.json` | 22 real Q&A cases, grounded in the actual PDFs, ready for Phase 6 |
| `postman/hrb_chatbot.postman_collection.json` | Every endpoint, importable, including idempotency/rate-limit/validation demo cases |

## Known gotchas - condensed, full detail in the docs above

- **Every `/rag/...` path is now `/v1/rag/...`** (`GET /health` is the one
  exception, deliberately unversioned). A fresh agent testing against an
  old memory of `/rag/documents` will get a `404`, not a bug.
- **Git Bash's MSYS layer mangles absolute Unix-style paths** (`/tmp/...`)
  passed to `curl -F` or AWS CLI args - corrupts them before the tool even
  sees them. Use relative paths from the repo root instead - see
  `README_TEST.md`'s own note on this.
- **The shell's working directory resets to a different project between
  tool calls** in this environment - always `cd` explicitly in the same
  command as anything using a relative path, or a `curl -F "files=@..."`
  silently fails with a confusing `curl: (26)` read error that looks
  unrelated to the real cause.
- **App Runner deployments failed twice before succeeding** - not a
  fluke, two independent real bugs (a hand-typed secret ARN missing its
  random suffix, and BuildKit's default image manifest format being
  incompatible with App Runner) - both root-caused and now permanently
  fixed in `deploy.yml`'s build command. Full story in
  `AWS-DEVOPS-RUNBOOK.md`'s "Three real bugs found the hard way."
- **The AWS identity used for all of this (`BedrockAgentCore` user) has
  full `AdministratorAccess`** on a shared personal AWS account that also
  hosts unrelated projects - used deliberately with the user's informed
  consent, not a mistake, but worth knowing before assuming every AWS
  action here is scoped down (the *deploying* identity is broad; the
  *deployed service's own* roles are deliberately narrow - see
  `AWS-DEVOPS-RUNBOOK.md`'s IAM section for the distinction).
- **In-memory state doesn't survive a restart**: the rate limiter and the
  idempotency-key cache are both single-process, in-memory - documented
  in their own module docstrings, not a surprise.

## Real resource identifiers - useless from memory, write them down

| What | Value |
|---|---|
| AWS account / region | `418884736369`, `us-east-1` |
| App Runner service (final, working) | `arn:aws:apprunner:us-east-1:418884736369:service/hrb-chatbot/f957548202f343aa8ca91f341d71d85a` → `https://mrgysvt6ye.us-east-1.awsapprunner.com` |
| ECR repo | `418884736369.dkr.ecr.us-east-1.amazonaws.com/hrb-chatbot` |
| GitHub repo | `https://github.com/rvsree/hrb_chatbot_v2`, branch `hrb_rag_pipelines` (only branch that exists remotely as of this writing) |

Full list including IAM role ARNs and Secrets Manager entries:
`AWS-DEVOPS-RUNBOOK.md`'s "Resource identifiers" section.

## Immediate next steps, ranked

1. **Nothing is broken or waiting on Claude Code right now** - the three
   items in [Blocked on the user](#blocked-on-the-user---three-concrete-items)
   are the only open threads, and none of them need code.
2. If continuing development: the natural next Claude-Code-owned work is
   Phase 6.1 (contracts/validation for the query path) - but it's
   **gated on Phase 6 existing first**, which is the user's hand-written
   work. Ask which hand-written phase (5.1 query decomposition, 6
   retrieval+generation, 7 guardrails, 8 evaluations/A/B harness) they
   want to tackle, rather than guessing.
3. If asked to "test everything" or "make sure nothing's broken": `cd`
   into the repo root and run `.venv\Scripts\python.exe -m pytest -v` -
   35 tests, all should pass with no setup beyond
   `pip install -r requirements-dev.txt`.

## Things worth remembering that don't fit neatly anywhere else

- The user is a Java-background developer explicitly learning Python and
  RAG concepts - code was refactored this session away from dense
  Python idioms (generator expressions in `sum()`/`all()`, terse
  ternaries) toward explicit loops/if-else, with comments explaining the
  Java-equivalent concept where one exists. Keep matching that density
  and that audience in new code, not reverting to terser idioms.
- The user explicitly asked "did you update requirements.txt?" at one
  point - a good habit worth continuing: state plainly whether a
  dependency file needed changes and why (or why not), rather than
  assuming it's obvious.
- Every commit in this repo ends with `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` - keep that convention.
- A pre-commit hook (`.githooks/pre-commit`) scans for real-looking API
  keys before every commit, opt-in via `git config core.hooksPath
  .githooks` - already enabled in this local clone. It had two real bugs
  in its own regex before landing on a version that correctly catches
  real keys without false-positiving on ordinary English text - worth
  reading its own comments before ever touching the pattern again.
