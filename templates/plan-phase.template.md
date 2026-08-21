<!--
PLAN PHASE TEMPLATE — the designer (plan mode, phase job) writes one of these per phase as
.devx/workstreams/{slug}/phases/{NN}-{slug}/plan.md.
SELF-CONTAINED: an implementer dispatched for this phase reads THIS file (plus project.md and its brief)
and nothing else from the plan. Put everything the build needs here; cross-reference, don't duplicate.
-->

# Phase {NN} — {title}

- Workstream: {slug}
- Depends on: {prior phases, or —}
- Objective: {what this phase achieves, 1–2 sentences}

## Approach
<!-- Chosen approach for this phase and why. Notable alternatives that were considered and rejected.
     Pointers to research files that informed the decision. -->
Chosen: {the approach picked for this phase + 1-line why}
Rejected: {notable alternative(s) + why not, or —}
Research: {pointers to phases/{NN}-{slug}/research/ files that informed it, or —}

## Context the implementer needs
<!-- Files/modules in scope, interfaces to honor, conventions, links to prior handoffs/research. -->
- In scope: {paths}
- Honor: {interface/contract/decision — link to decisions.md or a research file}

## Tasks
<!-- Small, independently reviewable. Each task's acceptance criteria are the failing tests AND the
     reviewer's rubric — write them testable, before any code.
     `Depends:` = prior task ids, or "none".
     `Writes:` = the normal source/config/doc files this task creates/edits — keep it TIGHT. Parallel
     dispatch requires disjoint Writes; overlap or unknown writes → sequence the conflicting tasks.
     `Reads:` = important context files this task reads only. Shared Reads never block parallelism.
     `Serialized resources:` = shared/generated/mutable resources this task needs exclusively
     (lockfile refresh, package install, migration generation/apply, route-tree generation, live DB/server).
     Prefer one owner step for each serialized resource instead of serializing unrelated source work.
     `Interfaces:` = the function/class signatures the implementer must honor, each with its responsibility
     and the key data shapes (inputs/outputs/errors) flowing across it. This is the planned decomposition
     contract — design it here so the implementer wires to it instead of inventing it.
     `Re-baselined from prior phase:` = OPTIONAL. Only when this task's acceptance evolves an EXISTING
     criterion from an earlier phase: "old criterion → new criterion + why valid". Makes an evolved
     criterion a visible tracked change, not a silently loosened test. Omit if nothing is re-baselined.
     `Risk:` = the main uncertainty/blast radius, or "low".
     `Verify (live):` = how the orchestrator proves the task works at runtime (stage-04 live-verify) —
     a command/endpoint/UI action + the expected observation, or "unit tests suffice — {why}" for
     non-runnable changes.
     Risk-tags: = which risk types this task introduces (research/security/ui/platform/architecture/docs), driving the orchestrator's per-phase specialist dispatch.
     Acceptance criteria: include >=1 negative-path/failure-mode criterion where the task validates input, authenticates, calls externally, or can fail. -->

### T01 — {title}  (size: S/M/L)
Depends: none
Writes: {normal files this task creates/edits — tight; split if it sprawls across files/modules/responsibilities}
Reads: {important context files read-only, or none}
Serialized resources: {lockfile/package install/migration apply/dev server/etc., or none}
Interfaces: {signature(s) the implementer must honor + each one's responsibility + key data shapes (in/out/errors); or "none — no new/changed interface"}
Re-baselined from prior phase: {old criterion → new criterion + why valid; or omit/— if nothing re-baselined}
Risk: {low | uncertainty/blast radius}
Risk-tags: [research|security|ui|platform|architecture|docs|none]   # which specialist passes this task may need (orchestrator-guide §13)
Acceptance criteria:
- [ ] {testable criterion — e.g. "returns 401 when the token is expired"}
- [ ] {testable criterion}
- [ ] {failure-mode criterion where applicable — e.g. "returns 400 when the payload exceeds 1 MB"}
- [ ] fix targets the ROOT CAUSE (no masking via wrappers / fallbacks / broad catches / special-cases) and carries a regression test that fails before the fix  # for bug-fix tasks
Verify (live): {command/endpoint/UI action + expected observation, or "unit tests suffice — {why}"}

### T02 — {title}  (size: S/M/L; depends: T01)
Depends: T01
Writes: {normal files this task creates/edits}
Reads: {important context files read-only, or none}
Serialized resources: {shared/generated/mutable resources, or none}
Interfaces: {signature(s) + responsibility + key data shapes; or "none"}
Re-baselined from prior phase: {old → new + why; or omit}
Risk: {low | uncertainty/blast radius}
Risk-tags: [research|security|ui|platform|architecture|docs|none]
Acceptance criteria:
- [ ] {testable criterion}
Verify (live): {…}

## Done when
- {phase-level exit: all tasks PASS-reviewed, suite green, any phase-specific live-verify done}

## Diagnostics applicability
<!-- Required for every phase. Canonical: references/contracts/diagnosability.md.
     A runnable product cannot use a generic N/A. Use the project's native logger; do not add a parallel
     telemetry stack or new DevX flag. -->
- Shape(s): {library | CLI | browser/frontend | desktop/mobile | service/API | worker/pipeline | distributed | N/A — specific non-runnable reason}
- Inherited diagnostics owner: {logger/telemetry module/config, or gap this phase must establish}
- Product control + destination: {LOG_LEVEL/config/standard app flag/settings control; stdout/file/support bundle/etc.}
- Events/errors/correlation: {stable event/error names; operation/request/job/trace propagation this phase changes}
- Privacy/resilience evidence: {redaction + log-injection + logger-failure/exception-boundary tests that apply}
- Verify (live): {action/command and the structured event/correlation/failure observation expected}
- Advanced N/A: {tracing | health | support bundle | crash upload — one-line applicability reason for each omitted item}

## GUI / visual (GUI tasks only — delete for non-GUI phases)
<!-- Include when this phase builds or touches a GUI component (desktop or web).
     If you DELETE this block for a non-GUI phase, add a one-line justification (e.g. "non-GUI phase —
     CLI/library only") so the deletion is a deliberate, visible choice. -->
- Demo mode: activatable without external deps, realistic sample data covers all major UI states [ ] yes / [ ] N/A
- Product Interface Direction: {`.devx/architecture.md#product-interface-direction` or exact inherited design authority}
- Changed views/states: {exact surfaces and default/loading/empty/error/success/disabled states}
- Reuse: {token module + shared components + representative accepted screen/gallery paths}
- Desktop/mobile composition: {what reflows/stacks/collapses/scrolls at 1440px and 375px, plus named viewport}
- Typography/action hierarchy: {heading/body/data roles; one clear primary action and secondary treatment}
- Text/accessibility: {long/localized text, 200% zoom, keyboard/focus/touch target, contrast pairs, theme variants}
- Assets: {source/provenance/license + dimensions/aspect ratio + alt behavior, or N/A}
- Motion: {purpose + reduced-motion outcome, or N/A}
- Expected gallery: {sanitized view-state screenshot names}
- Visual criteria (observable—not "modern", "beautiful", or "polished"):
  - [ ] {hierarchy/composition/token criterion tied to the Product Interface Direction}
  - [ ] empty/loading/error/success states render coherently without blank panes or placeholder text
  - [ ] EVERY interactive control (each button / menu item / toggle / list row / dialog / selector) is
        wired and produces its expected observable result — exercised via a REAL click/event, NOT a
        direct handler call. A rendered-but-unconnected or permanently-disabled control is a blocking defect.
  - [ ] 1440px + 375px (or desktop equivalents) screenshots and computed styles analyzed: hierarchy,
        rhythm, contrast, consistency, responsive recomposition, and no overlap/cutoff/overflow
