# Contract: Plan Check

**Canonical, single source** for the independent check of a *plan* (roadmap or phase plan): who performs
it, what it challenges, its verdict, cross-phase dependency reconciliation, and the re-baseline rule.
Stages, agents, and templates **point here** — they do not restate these. (The check of *code* is the
verify band — `phase-verification.md`. The handoff/evidence contract is `agent-guide.md`.)

## §P1 — Who checks the plan (independence)
A plan **cannot be self-graded by the context that produced it** — independence covers planning, not only
code. The initial plan-CHECK is performed by a **separate `devx:design:designer` running its plan-CRITIC
sub-behavior** in a clean context that did **not** see the planning rationale (sonnet; **opus** for a greenfield / GUI /
architecture / security-critical / concurrency / device-hardware / otherwise high-risk plan, per
orchestrator-guide §6). **The reviewer stays a pure code-checker and is not used for plan-CHECK.** The
plan-critic is handed the goal, roadmap, prior `phases/*/summary.md`, and the plan under review — never the
maker's PROPOSE/planning rationale. It acts only on objective findings in its inputs (never fabricates
operator feedback).

## §P2 — What the plan-CHECK challenges (every non-trivial roadmap / phase plan)
- **dependency order + the inversion rule** (§P4) — nothing a phase needs may be built after it
- missing prerequisites; downstream needs that should move earlier (or defer)
- hidden assumptions; weak or **missing-negative-path** acceptance criteria
- oversized tasks / overlapping `Writes:` / conflicting `Serialized resources:` / a module owning >1 of
  {UI render, navigation, worker lifecycle, I/O, domain policy, persistence, external device/API}
- missed safe fan-out: ready tasks serialized only because they share read-only context or a generated/global
  artifact that should have a dedicated owner step
- missing **interface decomposition** on a non-trivial task (functions/signatures/data shapes)
- missing UI / security / research `Risk-tags:`
- missing or generic **visual criteria** on a product-facing GUI: no inherited/approved Product Interface
  Direction pointer, subjective-only wording ("modern", "beautiful", "polished"), missing desktop/mobile
  composition or important states, or unproven asset provenance (`references/ui-design.md`)
- missing or incorrectly marked-N/A runtime-shaped **diagnosability** requirements and evidence
  (`references/contracts/diagnosability.md`)
- **re-baselined criteria that were not logged** (§P5)
- mismatch with the goal / definition of success

## §P3 — Verdict
**ACCEPT** or **REVISE** with concrete, criterion-anchored findings, written to
`.devx/workstreams/{slug}/roadmap-check.md` for a roadmap check, or
`.devx/workstreams/{slug}/phases/{NN}-{slug}/plan-check.md` for a phase check. A REVISE resumes the
**authoring designer** for **one** revise loop when orchestrator-guide §2a permits, then resumes this
producing critic for a full recheck. Each continuation gets a new immutable handoff; the critic appends a
recheck round rather than erasing its earlier verdict. Use a fresh fallback when the lineage is unavailable
or the revision materially changes scope, architecture, public interfaces, or acceptance criteria. The
orchestrator logs the verdict.
Implementation does not start on a plan that hasn't been ACCEPTed (or revised then accepted). The
plan-critic **critiques, it does not rewrite** the plan.

## §P4 — Cross-phase dependency reconciliation
Planning a phase reconciles dependencies **both directions**: confirm every prerequisite was delivered by a
prior phase (cite its `summary.md`), **and** scan the remaining roadmap rows for anything that must be stood
up earlier or deferred. The roadmap records each phase's **Needs / Provides** so ordering is checkable. A
required foundation appearing **after** the feature that needs it is an inversion — reorder or justify it.

## §P5 — Re-baseline rule (acceptance criteria evolve deliberately, never silently)
When a later phase legitimately invalidates a prior phase's acceptance criterion (a count, threshold, or
contract), **re-baseline it explicitly**: record `old → new` + the design change that justifies it in this
phase's `plan.md` and as a `DECISION` in `.devx/decisions.md`. **Never loosen a test in place** (e.g.
weakening an exact assertion to a soft invariant) to make evolved behavior pass. An undocumented loosened
test, or a phase criterion that relaxes a goal-level success condition without a logged `DECISION`, is a
`[BLOCKING]` review finding (`phase-verification.md` §V1) — this is where the reviewer enforces §P5.
