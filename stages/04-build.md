# Stage 04 — Build (the per-phase loop)

## Objective
Deliver the goal **one usable increment at a time**. Each phase is a full mini-lifecycle: research the unknowns → plan it just-in-time
(informed by everything prior phases built) → CHECK the plan → implement (one dispatch per task)
→ verify in order (functional → GUI + security) → fix → document → commit → plan the next phase. Repeat
until `roadmap.md` is complete. Runs hands-off
between the goal/scope gate (03) and ship (06); gate the operator only on a scope/roadmap change or the
**correctness floor**.

This stage follows the **PROPOSE → MAKE → CHECK → FIX** model policy (orchestrator-guide §6a): **opus**
reasons/designs and independently checks; an opus designer may write `.devx/` judgment artifacts, but
never product source. **Sonnet** makes product/source changes; **haiku** does plumbing.

## The per-phase loop  (repeat for each phase in `roadmap.md`, dependency order)
Work in `.devx/workstreams/{slug}/phases/{NN}-{slug}/` (`{NN}` = the two-digit zero-padded phase number,
e.g. `01`, `02`; a roadmap row may *label* a phase `P01` for humans, but the on-disk directory is
`phases/01-{slug}/`). `{HH}` below is the next zero-padded, workstream-unique handoff sequence; it is
separate from the phase number.

### 1. Plan THIS phase, just-in-time  — opus DIRECTS, designer MAKES
Read `goal.md`, `roadmap.md`, and **every prior phase's `summary.md`** (pointers, not full bodies) +
`project.md`/`architecture.md`. Reason about the approaches/areas this phase needs, then:
- **Research the unknowns** — dispatch `devx:research:researcher` (fan out several for parallel
  questions/areas) for any new library/API, platform/device behavior, packaging, or security assumption
  this phase introduces. Research lands in `phases/{NN}-{slug}/research/` (it is indexed → it ranks for
  later phases too). Give every question a distinct exact
  `return_as={HH}-researcher-{question-slug}.md`; validate all expected handoffs before planning consumes
  any of them.
- **Log/crash evidence route** — when live verification fails or the operator supplies logs/crash paths,
  apply `${CLAUDE_PLUGIN_ROOT}/references/contracts/diagnosability.md` §D6 before planning a fix: bound
  and normalize the untrusted evidence by dispatching `devx:recon:scout mode=diagnose-logs` with explicit
  evidence paths/time window/build/environment; it source-maps and writes `research/log-diagnosis.md`.
  Keep raw logs at their supplied/transient path. The designer plans from
  hypotheses + reproduction + failure fingerprint, never from an unlimited raw-log dump.
- **Write the phase plan** — dispatch `devx:design:designer` `mode=plan` (the MAKER) with the goal,
  roadmap, prior summaries, and the research, using a new exact
  `return_as={HH}-designer-plan-{NN}.md` → it writes `phases/{NN}-{slug}/plan.md`
  (`${CLAUDE_PLUGIN_ROOT}/templates/plan-phase.template.md`): small
  dependency-ordered tasks, **testable** acceptance criteria (incl. ≥1 negative-path), `Depends:`/
  `Writes:`/`Reads:`/`Serialized resources:`/`Risk:`/`Risk-tags:`/`Verify (live):`, and the **chosen approach
  + notable rejected alternatives**. For brownfield planning, set `Code-graph use: required`; it must locate
  existing owners/reuse candidates with MCP first, then verify them live. Every phase includes the
  template's `Diagnostics applicability`; UI phases also point to the approved/inherited Product Interface
  Direction and carry observable visual acceptance from `${CLAUDE_PLUGIN_ROOT}/references/ui-design.md`.
- `devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}`.

**Re-baseline inherited criteria (do NOT loosen in place).** If a prior phase's acceptance criterion (a
count, threshold, or contract recorded in its `summary.md`/`plan.md`) is now invalidated by what later
phases built, the designer must **re-baseline explicitly** — never silently relax a test from exact
behavior to a weak invariant. The plan records `old baseline → new baseline → the design change that
makes it valid → which tests/docs/screenshots move`, and the orchestrator appends a matching DECISION to
`.devx/decisions.md` (per orchestrator-guide). An undocumented loosened criterion is a CHECK/review block.

### 1b. CHECK the phase plan, independently  — opus DIRECTS, an initially clean CHECKer (read-only)
Before any implementation, the plan gets a CHECK analogous to the code verify band (orchestrator-guide §8 —
the planner can't self-approve). Dispatch a separate `devx:design:designer` running its **plan-CRITIC sub-behavior** (sonnet; **opus** on a
greenfield/GUI/architecture/security/concurrency/device or otherwise high-risk phase) in an initial **clean context**
that did **NOT** see the planning rationale, with `goal.md`, `roadmap.md`, the prior `summary.md` pointers,
and `phases/{NN}-{slug}/plan.md`, using a new exact
`return_as={HH}-designer-plan-check-{NN}.md`. It critiques the plan against the goal + constraints (not
the designer's self-justification) **per
`${CLAUDE_PLUGIN_ROOT}/references/contracts/plan-check.md` §P2** → writes
`phases/{NN}-{slug}/plan-check.md`, verdict **ACCEPT** or **REVISE** (§P3).
- `devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}`.
- **ACCEPT** → proceed to step 2.
- **REVISE** → **one** loop back by resuming the authoring designer (`mode=plan`) with the CHECK
  findings; it revises the plan, then resume the producing plan-CRITIC for one full re-CHECK. Every
  continuation gets a new exact `return_as` and rereads the current plan; use the fresh fallback in
  orchestrator-guide §2a when a lineage is unavailable or the revision materially broadens the baseline.
  An oversized task is **split in the plan here**, before any code is written
  (don't discover it at code review). A still-`REVISE` plan after one loop → escalate to the operator
  (it is a likely goal/scope signal → the 03 gate).

Phase plans are **not** individually operator-gated; a phase that forces a goal/scope change → back to
the 03 gate.

For product-facing GUI apps, early phases should be **minimum visually satisfactory vertical slices**:
the app can run, the primary screen/shell is styled enough for operator feedback, empty/error/busy
states are visible, and realistic/demo data exists when real data is not ready. Do not defer global
shell/design-system work to late polish if users must interact with the app during earlier phases.
Security/data foundations may be built first only when they are real prerequisites; the first visible
phase after them owns the visual baseline.

### 2. Implement  — implementer MAKES (sonnet)
**One dispatch per TASK** (`task_id`), not per phase. Each `devx:build:implementer` (sonnet) dispatch is a
small, reviewable unit with a small fix blast radius — pass `phase_path` (= `phases/{NN}-{slug}/plan.md`),
the single `task_id`, and `context_paths` (the research + prior summaries). **Never bundle multiple tasks
into one dispatch** unless the whole phase is tiny (a couple of trivially-coupled tasks on one small file
set). An oversized task is not handled here — it was **split in the plan** (step 1b); if one still looks
too large to implement-and-review cleanly, stop and bounce it back to a plan REVISE rather than building a
sprawling change.
- **Fan out** every currently-unblocked task whose `Writes:` paths and `Serialized resources:` do not
  conflict (several `Agent` calls in one message — see Parallelism). Run **`Depends:`-dependent tasks
  sequentially**, later tasks getting the earlier returns as context. Shared `Reads:` paths never block
  parallelism. Overlapping/`unknown` writes or serialized resources → sequence only those conflicting
  tasks. Before dispatch, allocate a distinct absent
  `return_as={HH}-implementer-{task_id}.md` for every task; fan-in only after every exact path passes
  `devx handoff_check`.
- Each task carries its own ownership, non-goals, acceptance criteria, and stop-conditions (from the plan).
The dispatch also carries `CODEMAP_PROJECT` and `Code-graph use: required | fallback | N/A — reason`.
The implementer follows `agent-guide.md` §3 **Reuse before creation**: when the task will create a new
function, class, component, module, route, API client, schema/helper, hook, service, policy, config
abstraction, or dependency, set `required` and search MCP first, then confirm against the live tree with
`Grep`/`Glob`, `rg`, or `ast-grep`. Use `fallback` only for an unavailable/stale graph. Exact-file edits,
plan-specified tokens/assets, docs, or static work with no new abstraction may be `N/A`. `handoff_check`
each return.

### 3. VERIFY BAND  — independent CHECKers (sonnet; opus on a high-risk/complex phase — see orchestrator-guide §6) (read-only), SEQUENCED
**Rules are canonical in `${CLAUDE_PLUGIN_ROOT}/references/contracts/phase-verification.md`** — severity
tiers (§V1), the sequenced band (§V2), the bounded fix-pass rule (§V3), the correctness floor + commit gate
(§V4), and checker independence (§V5). This stage gives the **step order + artifacts**; it does not
re-define those rules. Record each checker's gate commands (the `Command:`/`Verify (live):` lines) verbatim
in its artifact — the FIX pass re-runs those exact lines (§V3).

**3a. Functional code review FIRST** — `devx:review:reviewer` (sonnet; **opus** on a high-risk/complex
phase): re-runs the tests, scores criteria, runs **live-verify** (the project run command / harness
`verify`), tags findings `[BLOCKING]`/`[IMPORTANT]`/`[NOTE]` → `phases/{NN}-{slug}/review.md`. The reviewer
gets a new exact `return_as={HH}-reviewer-{NN}.md` with `Code-graph use: required`; it uses
`detect_changes`/`trace_path` or a focused symbol search for blast radius, then confirms live. The reviewer
**also runs an orphan scan** over the working tree (per code-standards "Finish clean"): a phase that
**replaces or supersedes** a component must **delete** the superseded module/view/directory **in this
phase** (an unreferenced module is dead code even if it never shows in the additive diff), and any leaked
phase-narration in production code (`Pxx`/`Txx` labels, `FP-FIX`, "MVP placeholder", task IDs) is a
finding to scrub. *Fix functional findings before the band proceeds* — go to step 4 for the functional set,
then return here once 3a passes. **Security may run inside 3a** (alongside the functional review) **only for
security-critical phases** with high early-design risk.

**3b. Once 3a passes — UI + security on the stabilized diff** (these two may run **in parallel with each
other**, each in an initial clean context independent from the maker):
- **GUI validation** — *only if the phase changed a UI*: `devx:ui:browser` (web → Playwright; **desktop**
  → its offscreen-screenshot recipe): empty / error / busy / scrolled / translated states, not just "it
  opened". It also verifies design quality against the Product Interface Direction, incumbent tokens,
  computed styles, prior accepted gallery, and bounded desktop/mobile captures per `ui-design.md`.
  **Live-verify exercises the phase's interactive controls via REAL events** (real clicks/keys/
  input — not calling handlers directly, not only capturing visual states); a rendered-but-unwired or
  permanently-disabled control is a **blocking** defect → `phases/{NN}-{slug}/gui.md`.
- **Security** — `devx:security:security` (sonnet; **opus** for a security-critical phase): review the
  phase diff with the **full data-flow route** (entry → sink) + dependency audit + secret scan →
  `phases/{NN}-{slug}/security.md`.

Give each checker a distinct exact `return_as` (for example `{HH}-browser-{NN}.md` and
`{HH}-security-{NN}.md`). Validate **both expected paths** after the parallel return; consolidate the 3b
findings, fix (step 4), then **re-verify** the band.

**3c. External second opinion only when materially useful (operator-gated).** After the internal checks and
stabilized diff exist, the orchestrator may recommend a Codex CLI code/security second opinion only when
the evidence still conflicts, the phase is security-critical/high-blast-radius, or the operator asks for
it. Ask first; default is decline. If approved, follow
`${CLAUDE_PLUGIN_ROOT}/tools-guide/native/codex-review.md` and write
`phases/{NN}-{slug}/codex-review.md`. The result is advisory evidence: independently reproduce any material
finding, never auto-apply it, and never use it instead of the normal reviewer/security artifacts.

### 4. FIX ×1 per verification return — owning implementer MAKES (sonnet)
Map the current finding set — functional 3a findings or consolidated 3b findings — back to task ownership.
Resume the exact original `devx:build:implementer` for findings local to its task/files. Disjoint owners
may each receive a non-overlapping subset once; overlapping writes remain sequential. If ownership is
ambiguous or the fix crosses task/interface boundaries, dispatch one fresh designated fixer with the
validated owner handoffs. Apply the assigned set in **one** pass per owner, using a new exact
`return_as={HH}-implementer-{task_id}-fix.md`,
per `phase-verification.md` **§V3** (re-run the **exact** recorded `Command:`/`Verify (live):` lines and
quote the real output; root cause, no masking layers) and **§V4** (every `[IMPORTANT]` is fixed **or**
deferred with an operator-logged `DECISION` + `.devx/backlog.md` link — never silently dropped; only
`[NOTE]` defers freely).

Then **re-verify by resuming the checker or checkers that produced the current findings**, plus any
checker whose evidence could have been invalidated. Each one rereads the current files/diff, reruns its
full recorded gate, scans the touched blast radius, appends a round, and classifies every finding
`FIXED | SURVIVES | REGRESSION`. After a localized 3b fix, resume the functional reviewer for regression;
use a fresh regression reviewer only when orchestrator-guide §2a's unavailable/broadened-scope fallback
applies. The orchestrator remains read-only and never grades the fix itself.
**Correctness floor (§V4):** if an acceptance criterion is still unmet, live-verify still fails, the review
is `REJECT`/has a surviving `[BLOCKING]`, or a **Critical/High** security finding survives → stop automated
progression and gate the operator. Functional failures must be retried, re-scoped, or aborted; they cannot
be risk-accepted as passing. A Critical/High security risk should be fixed and may proceed only after an
explicit operator acceptance recorded exactly as §V4 requires. Never commit a broken phase.

**The git committer enforces this floor (step 7).** The sole committer (`devx:vcs:git op=commit`) Reads
the phase's `review.md` + `security.md` and **refuses to commit** per the commit gate in
`phase-verification.md` §V4 (`REJECT` / unresolved `[BLOCKING]` / undispositioned `[IMPORTANT]` / surviving
**Critical/High** without an explicit recorded security-risk acceptance) — surfacing the refusal rather than
committing. The "1 fix pass per verification return, then escalate" discipline is what you run; the committer-gate
is the chokepoint that makes it stick (a phase that failed its gate cannot be committed).

### 5. Document + summarize  — docs MAKES (sonnet)
Dispatch `devx:docs:docs` `mode=sync`: update README / `architecture.md` / usage docs to match what
shipped, **and** write `phases/{NN}-{slug}/summary.md`
(`${CLAUDE_PLUGIN_ROOT}/templates/phase-summary.template.md`) — delivered surface, what's **reusable** for
later phases (`file:line`), decisions, verification, the verified **Diagnostics surface**, and what the
next phase must know. This summary is
the handoff that feeds the next phase's plan. Use a new exact
`return_as={HH}-docs-sync-{NN}.md` and validate it before reconciling state.

If the next roadmap phase has obvious independent research questions, dispatch those **read-only research
spikes in the background while docs sync runs** when their writes are disjoint (`phases/{NEXT}/research/`
vs this phase's docs/summary) and they do not depend on the current phase summary. Do not start full
next-phase planning until this phase's `summary.md` exists; the summary is an input to the plan. Join every
background research handoff by validating its pre-allocated exact path before the next phase plan consumes
it.

### 6. Reconcile and advance durable state
Update `roadmap.md` (mark `P` done). **The roadmap is the loop's only stop condition, so the loop may not
grow it without the operator:** reordering phases or *narrowing* a phase's scope within the
already-approved roadmap is autonomous, but **adding a phase, or expanding a phase's scope, is a roadmap
change → the 03 gate** (the operator owns the stop condition; the loop may not silently extend it).
Run `devx index --scope project` (so this phase's research + summary rank for the
next phase). Set `state.md` NEXT ACTION = "plan phase {P+1}" (the `P{N}` label → the on-disk directory
`phases/{NN}-{slug}/`, e.g. the NEXT ACTION "plan phase P02" creates `phases/02-{slug}/`), or `"ready to
ship"` when no phases remain. Log the phase transition, then run
`devx state check --workstream {slug}` and confirm `roadmap.md` · `state.md` · `log.md` · `summary.md` ·
review/security/UI verdicts agree. A reported `status_drift` blocks the phase close.

### 7. Commit the completed phase when VCS is enabled — git (haiku)
Read the VCS mode from `.devx/project.md`.
- `remote` or `local` → dispatch `devx:vcs:git` with `op=commit`, `commit_kind=phase`, `phase_id=P`, and
  the explicit accepted source/artifact paths plus a new exact
  `return_as={HH}-git-phase-{NN}.md`. The commit includes the already-reconciled roadmap/state/index
  pointers and phase artifacts; use a clean message with no AI attribution. Validate that exact handoff.
- `none` → skip the git agent. The reconciled `.devx/` state is still required.

### 8. Plan the NEXT phase — loop
Phases remain → go to **step 1** for `P+1`; otherwise → `06-ship`.

## Parallelism (within a phase)
Each task is **one** implementer dispatch (step 2). Prefer maximal safe fan-out: dispatch all ready tasks
whose `Writes:` paths and `Serialized resources:` are disjoint (several `Agent` calls in one message).
`Depends:`-dependent tasks run sequentially; shared `Reads:` paths do not block. Overlapping or `unknown`
writes/resources → **sequence the conflicting tasks only** (no mid-run merge safety: two agents editing one
normal source/config file is a lost write).

Do **not** serialize an entire phase merely because several tasks touch manifests, generated outputs, DB
state, dev servers, or lockfiles. Put those in `Serialized resources:` and assign one owner step to refresh
or apply the shared resource after parallel source-authoring tasks finish. Examples: package install /
lockfile refresh, route-tree generation, migration generation/apply, and live DB/server verification.

The verify band reviews the **phase** independently (orchestrator-guide §7) once its tasks are implemented
— review is per phase, not per task.

## Termination
**No cost/token cap.** The loop terminates *structurally*: when `roadmap.md` has no remaining phases.
Within a phase, work is bounded by one fix pass per verification return + the correctness-floor escalation — never an
infinite loop.

## Gates (only these)
- A phase forces a **goal/scope/roadmap** change → the 03 goal-&-scope gate.
- The **correctness floor** trips (step 4) → operator decision.
- A materially justified external second opinion is recommended (step 3c) → ask before invoking Codex;
  decline simply continues the internal workflow.
Everything else proceeds autonomously.

## Verification (stage exit)
- Every roadmap phase is done: plan → plan-CHECK → implement → verify-band (sequenced) clean → fix →
  docs+summary → state reconciled → committed when VCS is enabled.
- Full suite green; each phase's review/gui/security verdicts recorded; no Critical/High lacks remediation
  or the explicit operator security-risk acceptance required by §V4.
- `roadmap.md` shows all phases done; each phase has a `summary.md`; `state.md` says "ready to ship".

## Output artifacts
Per phase: `phases/{NN}-{slug}/{plan.md, plan-check.md, research/, review.md, gui.md, security.md,
summary.md}` plus optional `codex-review.md` only when operator-approved; source + tests; commits on
`devx/{slug}` when VCS is `remote`/`local`; updated `roadmap.md` and `state.md`
(+ `decisions.md`/`backlog.md` entries for any re-baseline, risk acceptance, or deferred `[IMPORTANT]`).

## Next
Read `stages/05-document.md` (skip to `06-ship` if the chosen path is quick-fix).
