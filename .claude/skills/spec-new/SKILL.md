---
name: spec-new
description: >
  Write a spec for a planned phase in hrb_chatbot_v2, before any code for it
  is written. Invoke as /spec-new <phase-name-or-number>, e.g.
  "/spec-new Phase 15" or "/spec-new evaluation". Also use this to promote a
  docs/BACKLOG.md item into a new phase entry with a spec.
argument-hint: "<phase name, number, or backlog item to promote>"
allowed-tools: Read Edit Grep
---

# Write a new spec

This project has no separate `specs/` folder - a spec is a `**Spec:**` block
written into the target phase's own bullet in `docs/RAG-ROADMAP.md`'s
`## Phases` section, **before** that phase's code starts. `docs/RAG-ROADMAP.md`
stays both the plan and the history in one file, matching how every phase in
it already works - a spec is just that same bullet, written earlier in the
phase's lifecycle instead of only after the fact.

## Steps

1. Find the target phase's `- [ ]` bullet in `docs/RAG-ROADMAP.md`'s
   `## Phases` section (or, if promoting a `docs/BACKLOG.md` item, add a new
   `- [ ]` bullet at the end of that section using the same
   `**Phase N (status) — Title.**` opening format every other bullet uses).
2. Append a nested `**Spec:**` sub-list to that bullet, using this template -
   omit a line if it's genuinely not applicable, but say so explicitly
   ("N/A - ...") rather than leaving it out silently:

   ```
   - **Spec:**
     - **Context:** why this phase, what triggered it.
     - **Data/API contracts:** request/response shapes this phase adds or
       changes - name the actual Pydantic model(s) in `src/hrb_chatbot/models/`.
     - **User-visible behavior:** what a caller can do after this phase that
       they couldn't before.
     - **Failure modes:** what's expected to go wrong and what the endpoint
       returns for each (status code + `error_codes.py` code).
     - **Retrieval quality criteria** (only for phases touching chunking/
       indexing/retrieval): chunking strategy and size, top-k/threshold,
       which `resources/golden_dataset/golden_dataset.json` rows cover it.
     - **Out of scope:** what this phase deliberately does not do.
     - **Open questions:** anything that needs a decision before or during
       implementation.
   ```

3. Set that phase's checkbox to `- [ ]` (not started) if it isn't already,
   and leave the "Status at a glance" table row's Status column as
   `📋 Planned` (or add the row if it's a newly promoted BACKLOG item).
4. Do not write any implementation code in this step. Report the spec back
   to the user for review before anything in `src/` changes - matches the
   "one task at a time" rule in `CLAUDE.md`.

## What "done" looks like

The phase's bullet in `docs/RAG-ROADMAP.md` now has a `**Spec:**` sub-list,
committed on its own before implementation starts, so the spec is reviewable
independent of any code diff.
