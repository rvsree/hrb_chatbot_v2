---
name: spec-implement
description: >
  Execute one already-reviewed phase spec from docs/RAG-ROADMAP.md end to
  end. Invoke as /spec-implement <phase-name-or-number>. For a scoped,
  isolated execution, use the implementer subagent instead
  (.claude/agents/implementer.md); this skill is the same checklist run
  directly in the main session.
argument-hint: "<phase name or number>"
allowed-tools: Read Edit Write Bash(.venv/Scripts/python.exe -m pytest *) Bash(git *)
---

# Implement a phase from its spec

Preconditions - stop and report if either is missing, don't proceed anyway:
1. The target phase has a `**Spec:**` block in `docs/RAG-ROADMAP.md` (see
   `/spec-new`). No spec, no implementation.
2. The spec has been reviewed (`/spec-review` run, or the user has
   explicitly said it's approved).

## Steps

1. Re-read the spec's "Data/API contracts", "User-visible behavior", and
   "Failure modes" sections - these are the acceptance criteria.
2. Implement in the smallest coherent slice that satisfies them, following
   `docs/CODING-STANDARDS.md` (or invoke `/coding-standards` explicitly on
   each new/changed file).
3. Write a test for every acceptance criterion in the spec - `tests/`
   mirrors `src/` 1:1.
4. Run `.venv\Scripts\python.exe -m pytest -v` - all tests pass, not just
   the new ones.
5. If anything in the spec is ambiguous or contradicts existing code, stop
   and ask rather than guessing - do not silently reinterpret the spec.
6. Update the phase's checkbox in `docs/RAG-ROADMAP.md` (`- [ ]` -> `- [x]`),
   its row in the "Status at a glance" table, and add a short "Verified:
   ..." line to the bullet describing what was actually checked - the same
   pattern every other completed phase in that file already follows.

Do not start a second phase in the same turn. One phase, reviewed, then
stop - matches `CLAUDE.md`'s "one task at a time" rule.
