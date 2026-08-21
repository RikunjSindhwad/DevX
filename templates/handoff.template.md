<!--
HANDOFF TEMPLATE — copy this, fill every {…}, delete the comments.
Write to: .devx/workstreams/{slug}/handoffs/{NN}-{agent}-{task}.md
This file is your ENTIRE output. It is summarized on purpose so the next worker starts from a
clean context, not a swelling conversation. Keep details on disk; keep pointers here.
Six fixed sections — do not rename or drop any. Use "none" where a section is empty.

Keep it short:
- Whole file: target under 120 lines.
- Summary: max 3 bullets or 4 short sentences.
- Changes: max 10 bullets; group related files by directory/module.
- Decisions: max 5 bullets; only choices downstream must know.
- Verification: max 8 bullets; quote summary lines, not full logs.
- Issues: max 5 bullets.
- Next: exactly one NEXT ACTION.
If you need more detail, write it to the owning artifact (`review.md`, `security.md`, `gui.md`,
`summary.md`, or `research/*.md`) and link that path here.
-->

# Handoff: {agent} — {task}
- Workstream: {slug}
- Target repo: {absolute target repo or git root}
- Code-graph use: {required | fallback | N/A — reason}
- Code graph check: {exact MCP tool + query + useful result, or fallback/N/A reason; never copy an unrun claim}
- Continuity: {initial | resumed — prior handoff path | fresh-fallback — reason}
- When: {ISO-8601 UTC}
- Status: {complete | partial | blocked}

## Summary
{Max 3 bullets or 4 short sentences: what changed and the outcome. No narration of process.}

## Changes
{Max 10 bullets. Files created/edited with paths; tests added; commands run. Group related files. `Docs touched:` is REQUIRED — state which docs changed, or `none — {reason}`, so the docs stage knows where drift is already handled. e.g.}
- `src/auth/token.py` — added `verify_token()` (rejects `alg:none`)
- `tests/test_token.py` — 4 cases (valid, expired, bad-sig, alg-none)
- ran: `pytest -q tests/test_token.py`
- Reuse check: {exact codebase-memory query/result + live rg confirmation, or fallback/N/A — reason}
- Docs touched: {e.g. README.md §Usage — added --dry-run flag} | none — {reason: internal refactor, no public surface change}

## Decisions
{Max 5 bullets. Choices you made + one-line why. What downstream must know — name the next agent (→ agent).}
- Chose PyJWT 2.9 over python-jose — maintained, fewer CVEs. → architect, recorded in decisions.md
<!-- If you need the orchestrator to dispatch help you cannot do yourself, end this section with: -->
### Orchestrator requests
- {specific need} because {how it blocks/weakens your work}   <!-- max 3; delete if none -->

## Verification
{Max 8 bullets. Tests/linters run + ACTUAL result summary. Acceptance-criteria status. Declare any test-first exception.
Include the required Evidence checkpoint from agent-guide §13.}
- `pytest -q` → 4 passed
- `ruff check` → clean
- Acceptance criteria: AC1 met, AC2 met
- Test-first: followed   <!-- or: "test-after — reason: hard-to-unit-test integration glue" -->
- Evidence checkpoint: confirmed — `tests/test_token.py::test_rejects_alg_none` failed before the fix and passed after; the test result supports sending this task to reviewer next

## Issues
{Max 5 bullets. What failed, was skipped, or is uncertain — or "none". One line each; point at `.devx/learnings.md` only
for DevX/process/prompt/sequencing/tooling/handoff/resource lessons. Product-code bugs point at the owning
handoff/review/security/summary/backlog artifact instead.}
- none

## Next
{Exactly one NEXT ACTION, blockers, and the exact files the next worker must read.}
- NEXT ACTION: {e.g. "implement the next ready task" or "start phase functional review"}
- Read: `.devx/workstreams/{slug}/handoffs/{NN}-{agent}-{task}.md`, `src/auth/token.py`, `tests/test_token.py`
- Blockers: none
