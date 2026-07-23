<!--
LEARNINGS INDEX TEMPLATE — the docs agent (distill mode) regenerates this from .devx/learnings.md.
Purpose: turn DevX/process failures (prompt, sequencing, tool-guidance, handoff, harness/plugin, and
orchestration-resource issues) into a few GENERALIZED, ranked patterns so a recurring process lesson
surfaces for the next agent. Product-code/domain bugs do not belong here. This file is DERIVED — never
delete learnings.md.
This file is FTS-indexed (devx index --scope project), so each pattern below ranks in kb_search.
-->

# Learnings Index — {project}

> Distilled from `.devx/learnings.md` on {ISO-8601 UTC}. Raw entries remain the source of truth.

## Patterns
<!-- One block per recurring root cause. Order by recurrence (most-hit first). -->

### P01 — {short pattern name, e.g. "Lockfile treated as phase-wide mutex"}
- **Lesson:** {the generalized takeaway — what's true beyond the one incident}
- **Recurrence:** {N} entries
- **Fix:** {what reliably resolves it}
- **Seen in:** {agent} {date}; {agent} {date}   <!-- back-pointers into learnings.md, for audit -->

### P02 — {…}
- **Lesson:** {…}
- **Recurrence:** {N} entries
- **Fix:** {…}
- **Seen in:** {…}

## By topic
<!-- Cross-cut so a reader scanning a domain finds the relevant patterns. -->
- **testing:** P01, …
- **build/deps:** P02, …
- **{topic}:** …

## By recurrence
<!-- The ranking that matters most: which mistakes keep happening. -->
1. P01 — {N} times
2. P02 — {N} times

## One-offs (not yet a pattern)
<!-- Single occurrences worth keeping visible but not yet generalized. Promote to a pattern on recurrence. -->
- {agent} {date} — {one-line lesson} → `.devx/learnings.md`
