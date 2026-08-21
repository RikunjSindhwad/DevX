# Stage 03 — Roadmap (goal + phase map)

## Objective
Define **what to achieve** and a **coarse map** to get there — *not* a frozen, fully-detailed plan.
Produce `goal.md` (the north star) + `roadmap.md` (one line per phase). Detailed phase plans are written
**just-in-time in stage 04**, each informed by what the prior phases actually built. This gate is
**always** presented — the operator owns the goal and the scope.

> Why not plan every phase now: a plan written before any code goes stale by phase 3. DevX plans the
> *destination* once, then plans each *leg* of the journey just before walking it (stage 04).

## Steps
1. Read the VCS mode from `.devx/project.md`. When it is `remote` or `local`, ensure a workstream branch
   exists by dispatching `devx:vcs:git` `op=branch` with a new exact
   `return_as={NN}-git-branch.md` (creates or resumes `devx/{slug}`). Validate that exact handoff before
   continuing. When it is `none`, skip all branch/commit dispatches; the `.devx/` workstream still records
   the lifecycle.
2. Dispatch `devx:design:designer` `mode=plan` with `brief.md`, `project.md`, and `decisions.md`/
   `architecture.md` (if present), using a new exact
   `return_as={NN}-designer-roadmap.md`. It authors **two artifacts only**:
   - `goal.md` — outcome + definition-of-success + constraints/non-goals
     (`${CLAUDE_PLUGIN_ROOT}/templates/goal.template.md`).
   - `roadmap.md` — a coarse, dependency-ordered phase map, **one line per phase** (what it achieves),
     NOT task breakdowns (`${CLAUDE_PLUGIN_ROOT}/templates/roadmap.template.md`). Each phase line also
     records, briefly, what it **needs** (prerequisites from earlier phases) and what it **provides**
     (what later phases will depend on). Order the roadmap so it satisfies these dependencies **both
     directions** — a required foundation is delivered before the phase that consumes it, and a need
     that a late phase will impose is surfaced early rather than discovered mid-build. A "needed in
     phase 2 but built in phase 5" inversion is a planning defect to fix here, not at review.
     For product-facing GUI apps, the roadmap must include an early **minimum visually satisfactory
     shell / first usable slice** that the operator can validate before many feature phases accumulate.
     Security/data foundations may precede it only when truly necessary; the first visible phase after
     that foundation owns the visual baseline, not a late polish phase. The first runnable product slice
     also establishes the applicable diagnosability floor; do not defer structured correlated evidence to
     a final hardening phase.
   …and initializes `state.md` (NEXT ACTION = "plan phase P01"). The `P01` label maps to the on-disk
   directory `phases/01-{slug}/` (the human-facing roadmap label `P01` → the zero-padded phase number
   `01` in the path — never `phases/P01-…/`).
3. Read its handoff, then run:
   ```bash
   devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}
   ```
4. **Plan-CHECK (independent, before the gate).** The goal/roadmap must be independently challenged
   before the operator approves — the planner can't self-approve (orchestrator-guide §8; this is the
   roadmap-level analogue of the per-phase plan-CHECK in §6b). Dispatch an **initial clean-context**
   checker that did **not** see the planning rationale — a separate `devx:design:designer` running its
   **plan-CRITIC sub-behavior** (the reviewer stays a pure code-checker), with a new exact
   `return_as={NN}-designer-roadmap-check.md`, given `critic_target=roadmap`,
   `goal.md`, `roadmap.md`, `brief.md`, and `project.md` only. It writes
   `.devx/workstreams/{slug}/roadmap-check.md` and challenges the roadmap against the goal + constraints (not the
   maker's justification) **per `${CLAUDE_PLUGIN_ROOT}/references/contracts/plan-check.md` §P2** (esp.
   dependency order + the inversion rule, missing prerequisites / body-parts, weak/missing criteria, UI
   quality). Use the strongest reasoning path (opus) for greenfield, GUI, architecture, security, or
   otherwise high-risk roadmaps. Validate the exact `return_as` handoff; fold blocking findings back to
   the designer before presenting the gate.

## Gate (always) — Goal & scope
Present `goal.md` (outcome + success definition + constraints) and the `roadmap.md` phase map via
`AskUserQuestion`: approve / adjust / re-scope. Surface the plan-CHECK's surviving concerns alongside,
so the operator decides with the critique visible. This is where the operator owns the **end result and
the scope**. Log `GATE` + `DECISION`. On change, resume the authoring designer under orchestrator-guide
§2a to update `goal.md`/`roadmap.md`, then resume the producing plan-CRITIC for the full recheck. Every
round gets a new exact handoff; use the documented fresh fallback when either lineage is unavailable or
the change materially re-baselines scope/architecture/criteria.

### Optional — external advisory critique
Offer (`AskUserQuestion`) a Codex CLI roadmap second opinion only when the internal plan evidence materially
conflicts, the roadmap is security-critical/high-blast-radius, or the operator asks for it. State the
reason and approved evidence; default is decline. If accepted, follow
`${CLAUDE_PLUGIN_ROOT}/tools-guide/native/codex-review.md` and write
`.devx/workstreams/{slug}/codex-roadmap-review.md` via inline `codex exec … -o …`. Treat the result as
advisory questions/risks only: independently verify retained claims, never auto-apply them, and never let
them steer architecture or scope without the normal operator gate.

> Phases are **not** individually gated — they are planned and built autonomously in stage 04. A later
> phase that forces a **goal or scope** change comes back to *this* gate.

## Verification
- `goal.md` states a checkable outcome + success definition + constraints/non-goals.
- `roadmap.md` lists dependency-ordered phases, one coarse line each (no task detail), each noting
  what it **needs** / **provides**; no dependency inversion survives.
- The initial plan-CHECK ran in a separate clean lineage (not self-graded), `roadmap-check.md` records its verdict/findings,
  and its blocking findings were resolved.
- `state.md` NEXT ACTION points at planning the first phase.
- In `remote`/`local` VCS mode the workstream branch exists; in `none` mode no git agent was dispatched.

## Output artifacts
`.devx/workstreams/{slug}/goal.md` + `roadmap.md` + `roadmap-check.md`, updated `state.md`, optional branch
`devx/{slug}` (`remote`/`local` only), designer handoff, plan-CHECK handoff (+ optional
`codex-roadmap-review.md` if the operator accepted).

## Next
Read `stages/04-build.md` — the per-phase loop.
