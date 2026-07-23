# Stage 01 — Design (optional: brainstorm + architect)

## Objective
Make the up-front design decisions: **what to build with** (stack/packages) and **how to structure it**
(modules/boundaries). Two passes of the **`devx:design:designer`** agent — `brainstorm` then `architect`
— each optional and each with its own operator gate. Run for greenfield or a substantial new feature;
**skip** for localized changes to an existing codebase (note the skip in `state.md` and go to `03-plan`).
Run only the pass(es) the work needs: a new framework/package needs `brainstorm`; a structural change
needs `architect`; a brand-new subsystem needs both.

## Pass A — brainstorm (stack & packages) → `.devx/decisions.md`
Run when the work introduces a stack/runtime/framework/package choice or the direction is unclear.
1. Dispatch `devx:design:designer` **`mode=brainstorm`** (sonnet) with the `brief.md` path and
   `.devx/project.md`, using a fresh exact `return_as={NN}-designer-brainstorm.md`. It searches the vault's
   package-selection guidance, verifies current versions with `devx fetch`, checks real usage with
   `devx github_search`, and appends choices to `.devx/decisions.md`.
2. On return: `devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}`.
3. If the handoff surfaced a close, high-impact fork in `### Orchestrator requests`, carry it into the
   gate below with the recommendation and the "choose B if …" condition.

**Gate (Direction).** Present the recommended stack + key packages (verified current versions, version
policy, one-line rationale each) via `AskUserQuestion`: approve / adjust / pick an alternative. Present any
human-choice fork as a decision (recommended option, alternative, tradeoff, condition), not an open
question. Log `GATE` + `DECISION`. On change, dispatch `designer mode=brainstorm` to update `decisions.md`.

## Pass B — architect (structure) → `.devx/architecture.md`
Run when the work creates or changes module structure / public interfaces / dependency direction.
1. Dispatch `devx:design:designer` **`mode=architect`** (sonnet) with `decisions.md`, `project.md`, and the
   current `architecture.md` (if any), using a fresh exact
   `return_as={NN}-designer-architect.md`. For a genuinely hard greenfield design, override the model to
   **opus** at dispatch (orchestrator-guide §6).
2. It defines modules, boundaries, interfaces, dependency direction, and testing seams, and writes
   `architecture.md` with rationale (centralized domain policy; an explicit lifecycle for GUI/long-running
   apps — architecture-principles).
3. On return: `devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}`. Note
   any follow-on work for the plan stage.

**Gate (Architecture).** Present the proposed structure (modules + key interfaces + the main tradeoff) via
`AskUserQuestion`: approve / adjust. Log `GATE` + `DECISION`.

## Verification
- If brainstorm ran: `.devx/decisions.md` lists the chosen stack with verified current versions, version
  policy, rationale, and each major choice's alternative + tradeoff.
- If architect ran: `.devx/architecture.md` matches the chosen stack and (brownfield) the real repo;
  boundaries, interfaces, and dependency direction are explicit; structure is minimal (no speculative scaffolding).
- Any skipped pass has a one-sentence skip rationale in `state.md`.

## Output artifacts
Updated `.devx/decisions.md` and/or `.devx/architecture.md`; designer handoff(s).

## Next
Read `stages/03-plan.md`.
