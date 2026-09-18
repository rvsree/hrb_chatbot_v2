---
name: spec-review
description: >
  Audit one phase's spec in docs/RAG-ROADMAP.md for completeness before
  implementation starts. Invoke as /spec-review <phase-name-or-number>.
argument-hint: "<phase name or number>"
allowed-tools: Read Grep
---

# Review a spec for completeness

Find the target phase's `**Spec:**` sub-list in `docs/RAG-ROADMAP.md` (see
`/spec-new` for where it lives) and check it against the template every spec
should follow:

| Section | Present? | Note |
|---|---|---|
| Context | | |
| Data/API contracts | | Are the actual Pydantic model names given, not just "a request model"? |
| User-visible behavior | | |
| Failure modes | | Does it name real `error_codes.py` codes, not just "an error"? |
| Retrieval quality criteria | | Only required if the phase touches chunking/indexing/retrieval - flag as N/A otherwise, don't require it |
| Out of scope | | |
| Open questions | | An empty list here is fine; a missing section is not |

Also check:
- Does anything in "Data/API contracts" conflict with an existing model in
  `src/hrb_chatbot/models/`? Flag it - don't resolve it.
- Does anything in "User-visible behavior" already exist? Flag possible
  duplication with an already-shipped phase.
- Is there a `docs/FAQ.md` entry that already answers one of the "Open
  questions"? Point to it instead of leaving the question open.

Report a short PASS/NEEDS-WORK verdict per section, not a rewrite of the
spec. The user decides what to fix before implementation starts.
