<!--
ROADMAP — write to .devx/workstreams/{slug}/roadmap.md. The COARSE phase map toward goal.md.
ADAPTIVE, not frozen: phases are planned JUST-IN-TIME, one at a time, in stage 04 (each phase's detail
lives in phases/{NN}-{slug}/plan.md, written right before that phase is built). Update this map as phases
complete and as you learn — a phase may be added, dropped, or re-scoped. A change that alters SCOPE
(not just sequencing) is an operator gate.
Keep each row to ONE line (what the phase achieves). Do NOT put task breakdowns here.
`Needs:` = what this phase depends on from EARLIER phases (or "—" for none).
`Provides:` = what this phase delivers that LATER phases depend on (or "—").
Make cross-phase dependencies explicit so order is checkable both ways: every `Needs:` must be satisfied
by a `Provides:` of an EARLIER phase. A foundation that appears AFTER the feature needing it (a
"needed in P2 but built in P5" inversion) is a planning error — reorder or justify it in the Log.
-->

# Roadmap — {workstream}

Goal: see `goal.md`. Phases are planned just-in-time; this is the map, not the plan.

| Phase | Achieves (coarse, one line) | Needs (from earlier phases) | Provides (to later phases) | Status |
|---|---|---|---|---|
| P01 | {what this phase delivers toward the goal} | — | {what later phases can build on} | next |
| P02 | {…} | {what it needs, from which phase} | {…} | not-started |
| P03 | {…} | {…} | {…} | not-started |

<!-- Status ∈ next | in-progress | done | re-scoped | dropped -->

## Log
<!-- one line per phase boundary: done / re-scoped / added, + date -->
- {date} — roadmap drafted ({N} phases)
