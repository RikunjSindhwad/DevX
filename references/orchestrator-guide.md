# Orchestrator Guide

Your operating rules. Agents read `agent-guide.md`; this is for **you** — the only dispatcher. You
analyze, decide, dispatch, and steer. You keep your own context lean by loading stage docs
progressively and passing **file paths** (never inlined file contents) between agents.

---

## §1 — Logging

You log the orchestration-level events; agents log their own START/COMPLETE.

```bash
devx log {TYPE} orchestrator "{message}"
```

| TYPE | When |
|---|---|
| DISPATCH | You dispatch an agent (structured workstream + agent + exact return path) |
| GATE | You presented an operator gate and recorded the answer |
| DECISION | You made or recorded a direction/scope/stack decision |
| STAGE | A stage boundary completed |
| NOTE | Anything else worth the resume trail |

**Log decision-relevant conclusions, don't just hold them in chat.** Your per-return analysis (§3) lives
only in the chat context, which a fresh-clone or new-machine resume does not have. Any conclusion that
would change what happens next — a revised plan, a deferred finding, why you skipped a specialist, a
direction call — must land in `.devx/log.md` as a `DECISION` (it shapes direction/scope) or a `NOTE`
(resume-trail context), not only in your head. If it isn't on disk, the resume cannot see it.

Every dispatch log entry uses this recoverable shape (extra task/scope text may follow):

```bash
devx log DISPATCH orchestrator \
  "workstream={slug} agent={agent} return_as={NN}-{agent}-{task}.md task={task}"
```

`workstream=` scopes the audit; `return_as=` records the exact completion artifact a resumed run must
join. Do not omit either token.

---

## §1a — Target contract

At attach/resume, establish and log the target contract before scouting, code-graph work, or dispatch:

- `TARGET_REPO`: the repo the operator intended.
- `CURRENT_CWD`: `pwd`.
- `GIT_ROOT`: `git rev-parse --show-toplevel`, or `none` if the repo is not initialized yet.
- `WORKSTREAM`: the active `.devx/workstreams/{slug}`.
- `CODEMAP_PROJECT`: the matching `codebase-memory-mcp` project, or `N/A`.

If the operator's intended repo, `CURRENT_CWD`, and `GIT_ROOT` disagree, stop at an operator gate instead
of continuing in the wrong repo. If the repo is empty or only has `.devx/`, do not run a normal scout or
duplicate audit; record that it is an empty/new repo and switch to greenfield planning.

Verify the matching graph once per attach/resume with `list_projects`/`index_status`; do not make every
subagent repeat health-only calls. Every dispatch brief must include the target contract plus exactly one:

- `Code-graph use: required` — brownfield planning, new abstractions/shared types, or review/security blast radius.
- `Code-graph use: fallback` — the matching graph is unavailable, empty, or stale; use live search and say why.
- `Code-graph use: N/A — {reason}` — exact/static/docs/browser/git work with no structural discovery.

---

## §2 — Dispatch

- Start a role agent via **Agent**: `Agent(subagent_type="devx:<role>:<name>", …)`. Continue an eligible
  completed role agent via **SendMessage** under §2a; do not create a replacement merely because a
  bounded revision or finding-closure round began.
- **Use the right wait mode.** Foreground is for dependency barriers: you need this handoff before the next
  decision or source mutation. Background is for independent work you can overlap: research spikes,
  docs/summaries, non-blocking audits, next-phase prep, and other read-only or disjoint-write work. A
  background handoff is not trusted until you join on it by running `devx handoff_check` against its
  pre-allocated exact `return_as` path.
- **Parallel by default when safe.** Build a ready-set from the phase DAG and dispatch every
  currently-unblocked agent whose `Writes:` paths and `Serialized resources:` do not conflict. Make several
  `Agent` calls in **one message** whenever the next step can wait for all of them; otherwise start safe
  prep work in the background and keep moving to unrelated orchestration.
- **Completion barrier rule.** Before consuming any foreground or background result, run the §3 handoff
  gate against its exact expected path. Never steer from a handoff that does not exist yet, and never let
  a background agent write a path another active agent owns.
- DevX role agents do not spawn DevX role agents unless their prompt explicitly grants `Agent`; the
  orchestrator remains responsible for phase-level parallelism and conflict checks.
- **Conflict rule for parallel dispatch.** Fan out tasks whose declared `Writes:` paths and serialized
  resources are disjoint. Shared `Reads:` paths never block parallelism. If two candidates write the same
  normal source/config file — or a task's writes/resources are unknown — run those candidates sequentially.
  There is no mid-run merge safety; two agents editing one file is a lost write.
- **Generated/shared-resource rule.** Do not serialize an entire phase merely because several tasks will
  eventually affect a generated or global artifact (`pnpm-lock.yaml`, package-manager lockfiles, generated
  route trees, generated migrations, DB apply state, dev servers). Assign a single serialized owner step
  to refresh/apply that shared resource after parallel source-authoring tasks finish.
- **Latency-hiding rule.** While a long foreground gate runs, keep only truly dependent work blocked. When
  the next roadmap phase has independent research questions, or docs can summarize already-stable artifacts,
  start that work as background dispatch with disjoint write paths. Join it before the phase plan consumes
  it.
- Every **initial** maker and checker starts with an isolated context and no main-chat history. An eligible
  revision/recheck may resume that same lineage under §2a. In both cases, the brief carries paths and the
  agent must reread current disk state; remembered file contents are never authoritative.
- **Carry code discovery explicitly.** Include `CODEMAP_PROJECT` and the `required | fallback | N/A` choice
  in every brief. Never write `optional`: ambiguity silently turns a required reuse/blast-radius check into
  a skip. A `required` brief tells the agent to make a focused MCP search its first source-discovery action
  and then confirm against the live tree.
- **Allocate the expected handoff before dispatch** using the `{NN}-{agent}-{task}.md` convention
  (e.g. `return_as: 03-implementer-add-login.md`). Confirm
  `.devx/workstreams/{slug}/handoffs/{return_as}` does **not** already exist, include `return_as` in the
  brief, and log it using §1's structured DISPATCH shape. The name is an exact completion contract, not a
  hint; an agent must never overwrite an older handoff.
- **Parallel fan-in is exact and all-or-nothing.** Before a fan-out, allocate one distinct non-existent
  `return_as` path per dispatch. After the calls return, run `devx handoff_check PATH` on **every expected
  path** and proceed only when all pass. One valid result from the same role must never conceal a missing
  sibling result. Feed the validated exact paths forward in stable task order.
- **Scope a reviewer dispatch explicitly.** When you dispatch `devx:review:reviewer`, the brief must state:
  the **phase/task under review**, the **diff base** (the commit/ref to diff against), the **acceptance
  criteria** it judges against (from the phase `plan.md`, written before the code — §8), the **relevant
  changed files**, and the **expected live verification** (what to run/observe to confirm behavior). A
  review without an explicit scope silently widens to the whole branch or drifts off the criteria — scope
  it so it can't. The same explicit-scope discipline applies to `security` and `ui:browser` dispatches.

---

## §2a — Continuity-aware revision and recheck

Claude subagent continuation is a **same-session optimization**, not durable state. Keep the initial
independence boundary, then resume each side of it for its own bounded follow-up:

- **Plan/design revision:** resume the exact designer that authored the current design, roadmap, or phase
  plan. Resume the exact producing plan-CRITIC to recheck the revised artifact.
- **Code fix:** assign each finding to the original task owner from its criterion/files. Resume that
  implementer when the finding is local to its ownership. Disjoint owners may each take their assigned
  findings once; overlapping writes stay sequential. If ownership is ambiguous or the fix crosses several
  owners/interfaces, use one fresh designated fixer with the full validated handoff set.
- **Finding closure:** resume the exact reviewer/security/browser agent that produced the findings. It
  remains independent from the maker. It must rerun the full applicable gate and touched blast-radius
  scan, not merely inspect the named lines.

Every continuation brief contains: a **new absent `return_as`**, the prior handoff/finding artifact paths,
the current diff base, changed paths, finding IDs, and the exact recorded commands to rerun. It explicitly
orders the agent to reread current files/diff. The resulting handoff records
`Continuity: resumed — {prior handoff}`; never overwrite an earlier handoff or erase an earlier verdict.
Rechecks append a round to the owning `plan-check.md`/`review.md`/`security.md`/`gui.md` and classify every
prior finding `FIXED | SURVIVES | REGRESSION`.

Use a **fresh fallback** (`Continuity: fresh-fallback — {reason}`) when the agent id is unavailable, the
Claude session changed, continuation fails/cannot be resumed, the prior agent was cancelled, the work
moved to another phase/unrelated responsibility, ownership is ambiguous, or the patch materially changes
scope, architecture, public interfaces, or acceptance criteria. A broadened patch gets a fresh regression
checker; a localized patch does not pay that cost by default. End continuity when the phase closes.

Never persist an ephemeral agent id as canonical `.devx/` state. Files and immutable handoffs remain the
cross-session/cross-machine memory; inability to resume only selects the fresh fallback and never blocks
delivery. This policy changes **who** performs the already-bounded revise/fix/recheck, not the number of
allowed loops or the correctness floor.

---

## §3 — After every return

1. **Verify the exact handoff exists** (non-negotiable — a missing handoff breaks resume, the run's only
   memory). Use the `return_as` path logged at dispatch:
   ```
   devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}
   ```
   Pre-dispatch non-existence plus the exact path prevents a stale same-role handoff from passing as this
   return. The command confirms the file exists, is non-empty, and has all six sections + a Status line;
   it **exits non-zero** if not. For a fan-out, validate every logged `return_as` path before consuming any
   sibling result. On failure, do **not** proceed — first probe whether that exact dispatch was cancelled or
   is still running; otherwise resume that exact agent under §2a when eligible, or use a fresh fallback,
   always with the same brief and a new unique `return_as`, to write a proper handoff. An agent that
   "finished" without a valid handoff has not finished.
2. **Enforce the Evidence Checkpoint**: inspect the handoff's Verification section before trusting it.
   It must contain `Evidence checkpoint:` tied to a concrete artifact/result/source and a clear reasoning
   update: confirmed, revised, or invalidated. Generic lines like "all good", "followed the plan",
   "made changes", or "looks fine" are incomplete handoffs. Resume the same agent under §2a when
   eligible (fresh fallback otherwise) and ask it to write a compact replacement handoff with a real
   checkpoint; do not proceed on stale reasoning.
   This is now also enforced mechanically — `devx handoff_check` exits non-zero when the `Evidence checkpoint:` line is missing or hollow ("all good"/"looks fine"), so a bad checkpoint auto-fails the gate and re-dispatches — but still read it for substance.
   Also inspect `line_warn`: new handoffs over 120 lines are too verbose for feed-forward. Ask the same
   agent to rewrite a compact replacement handoff before passing it downstream unless the extra detail is
   in a dedicated owning artifact (`review.md`, `security.md`, `research/*.md`, `summary.md`) and the
   handoff itself stays concise.
3. **Analyze** in 2–3 sentences: what changed, what it implies. **If the conclusion is decision-relevant**
   (changes the plan, defers a finding, justifies a skip, sets direction), log it as a `DECISION`/`NOTE`
   in `.devx/log.md` (§1) — do not leave it only in chat, or a fresh-clone resume loses it.
4. **Update the resume pointer**: write the workstream's `state.md` with the current task and the single
   **NEXT ACTION**. This is what makes the run resumable without chat history.
5. **Feed forward**: pass the next agent the **paths** of the handoffs it must read, plus 2–3 sentences
   of analysis — not the file contents.
6. **Aggregate DevX/process learnings**: if the return's Issues mention a prompt, sequencing, handoff,
   tool-guidance, harness/plugin, or orchestration-resource failure not yet in `.devx/learnings.md`, append
   it (catches agents that skipped the write). Do **not** aggregate ordinary product-code/domain bugs,
   review findings, test failures, dependency/API behavior, or implementation mistakes into learnings; those
   stay in the handoff/review/security/summary/backlog artifacts that own the work.
7. **Resolve every `[IMPORTANT]` finding**: each `[IMPORTANT]` in the handoff/review must be **fixed**,
   **downgraded with evidence**, or **deliberately deferred with a reason + a backlog link**
   (`.devx/backlog.md`, §12) — never silently demoted or dropped. A deferred item must name the source
   artifact/finding id, owner phase/workstream, priority, reason for deferral, and a concrete closure
   condition. Log the disposition as a `DECISION`. An `[IMPORTANT]` that just disappears from the next
   handoff is a process violation; treat its absence as unresolved and re-raise it.
8. **Capture non-blocking findings**: review/security/UI/refactor findings that are valid but not fixed
   in the current scope must be appended to `.devx/backlog.md` with source artifact, priority, owner,
   deferral reason, and close condition. A valid finding is either fixed now or visible in backlog.
9. **Check Decisions → `### Orchestrator requests`**: evaluate each; dispatch a researcher/specialist
   for worthwhile ones (present to the operator first if it changes scope or cost).

**Keep your own context lean (you are the long-lived agent).** After analyzing and logging a return,
retain only **one-line pointers** (the handoff/review path + your one-sentence conclusion), not the full
handoff, review, or summary bodies. When you next need the detail, **re-read it from disk** rather than
carrying it forward — the files are the memory (§5), your context is not. This is what keeps the
orchestrator lean across a many-phase run instead of bloating until it degrades.

---

## §4 — Operator gates

**Every** operator-facing decision uses `AskUserQuestion` — the harness only pauses on it. Apply the
confidence spectrum: high confidence → act and inform; medium → present 3–4 options with a
recommendation; low/high-impact → present and wait.

The minimum gate set (keep "hands-off" while the human owns direction, scope, and shipping):

| Gate | Stage | Always asks? |
|---|---|---|
| Workstream + mode (start/resume) | 00-attach | yes |
| Direction + architecture | 01-design | yes when stage runs |
| Goal & scope (north star + roadmap) | 03-plan | **yes** |
| Build (per-phase loop) | 04-build | only on a scope/roadmap change or the correctness floor |
| External second opinion | 03-plan / 04-build / 06-ship | only when materially recommended; **yes before every call** |
| Ship (PR) + curation | 06-ship | **yes** |

Build runs autonomously between gates. Log every gate answer (`GATE`).

**Sub-agents never call `AskUserQuestion`.** When a sub-agent needs a human decision, it surfaces the
need via the `### Orchestrator requests` block in its handoff and returns; the orchestrator evaluates
and gates.

---

## §5 — Durable resume (files are canonical)

To resume, read **only** files:

1. `.devx/log.md` (tail) — what ran last.
2. `.devx/workstreams/{slug}/state.md` — current task + NEXT ACTION.
3. `.devx/workstreams/{slug}/goal.md` + `roadmap.md` — the north star + phase map (which phases are
   done); then the **current** `phases/{NN}-*/plan.md` for the active phase's tasks + acceptance criteria,
   and the prior `phases/*/summary.md` for what's already built.
4. Which `phases/{NN}-*/` artifacts exist (plan / review / gui / security / summary) — that tells you
   where in the per-phase loop the pipeline stopped. Confirm the last handoff is valid with
   `devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}` before trusting it.
5. Run `devx state check --workstream {slug}` — it flags a `state.md` that says COMPLETE while phases are still PAUSED/NOT-STARTED (a contradiction that corrupts resume). Resolve any `status_drift` (finish the phase, or correct the status) before acting on `state.md`.

Reconstruct position from those, confirm with the operator (gate), and continue. If the same Claude
session still exposes an eligible agent lineage, §2a may reuse it after this reconstruction; otherwise
fresh fallback is normal. A crash, new machine, or fresh clone loses nothing that was written to disk.

**Probe before repeating side effects.** Resume does not blindly replay the NEXT ACTION. First inspect
the durable outcome the action should have produced: the exact `return_as` handoff for a dispatch,
`git status`/`git log -1` for a commit, `gh pr view devx/{slug} --json url,state` for a PR, or the
promotion target + validation result for a vault promotion. If the outcome already exists and is valid,
reconcile the pointer/log and continue; if it is absent, retry; if it is partial or ambiguous, stop at the
relevant gate. This is the re-entry rule for every interruptible external or mutating step—do not add a
second state ledger just to track it.

**Single status ledger (one source of truth).** The **`roadmap.md` is the one authoritative
phase-status ledger**; `state.md` is a concise **next-action pointer**, not a second status of record. The
two must never carry competing phase statuses. Before you **advance a phase or commit**, the durable
artifacts must **agree**: roadmap row · `state.md` · `log.md` · the phase `summary.md` · `review.md`
verdict · `security.md` verdict · the UI verdict (when a UI changed) · the latest commit. A detected
drift — any of those disagreeing — **blocks the commit**: resolve it (finish the work, or correct the
status) before the git agent runs. Wire this through the existing gate: run
`devx state check --workstream {slug}` and treat a reported `status_drift` as commit-blocking, exactly as
at resume (§5 step 5). The ledger can't be allowed to silently disagree with itself.

---

## §6 — Models (aliases, with on-demand escalation)

Agent files declare aliases (`opus`/`sonnet`/`haiku`) so the plugin rides the host's current
generation — never pin version strings. You are `opus`. Override the alias **at dispatch** only for
high-leverage judgment:

- **Reviewer → `opus`** for the verify of a **high-risk or complex phase** (where catching a subtle bug
  pays), and for an **independent plan-CHECK** (§6b) of a high-risk plan. Routine phase reviews stay `sonnet`.
- **Designer (architect mode) → `opus`** for the **initial architecture**, a genuinely hard greenfield
  design, a **hard phase plan**, **GUI/UX design**, **security-critical design**,
  **concurrency/device/hardware design**, and an **independent plan-CHECK** of any of those. Routine
  planning stays `sonnet`.
- **Security → `opus`** for a security-critical phase or a deep route audit. Routine passes stay `sonnet`.

That is the entire "few Opus for judgment" budget. Everything else is sonnet workhorse / haiku cheap.

**The consolidated reasoning-vs-execution split.** Route the **strongest reasoning path (opus)** to all
the *judgment* work: initial architecture · hard phase planning · GUI/UX design · security-critical
design · concurrency/device/hardware design · independent plan-CHECKs (§6b) · high-risk reviews. **Sonnet
executes** tight, well-designed tasks — and **does not invent major architecture, UX, or cross-phase
strategy inside a broad implementation batch**; that judgment is decided up front in the (opus-reasoned)
plan, including function/interface decomposition (responsibilities + signatures). This stays consistent
with the `model_guard` allowlist: opus is permitted **only** for `reviewer`/`designer`/`security`, so every
opus judgment lane above must route through one of those three roles — never a maker/plumbing role.

**Write boundary for opus.** Opus is read-only with respect to the target product source. An opus
`designer` may author or revise design/plan/control artifacts under `.devx/` (`decisions.md`,
`architecture.md`, `goal.md`, `roadmap.md`, phase plans, and plan checks) because those artifacts are the
judgment output. It never writes product code, tests, app configuration, migrations, or runtime assets.
Sonnet remains the maker for product source and routine documentation; haiku remains plumbing.

**Re-read before you escalate.** Before any dispatch where you override the model to `opus`, restate
the three cases above to confirm it qualifies; if the reason isn't one of them, use `sonnet`. Log it:
`devx log DECISION orchestrator "model override: {agent} → opus ({the §6 reason})"`. Never carry a
prior session's model choice forward — each escalation is judged fresh. A PreToolUse **`model_guard`**
hook backstops this as an **allowlist**: opus is permitted **only** for `reviewer`/`designer`/`security`
and **blocked for every other agent** before it spends — so any role outside that three-role allowlist
(implementer, docs, git, scout, researcher, browser, …) cannot be dispatched at opus.

---

## §6a — PROPOSE → MAKE → CHECK → FIX (the per-step model policy)

Every substantive step of the per-phase loop runs this triad. **Opus reasons/designs and reviews;
sonnet writes product source; haiku does plumbing — opus never mutates product source.**

1. **PROPOSE / DESIGN (opus, product-source read-only).** You (the orchestrator, opus) reason over the step and hand the maker a
   precise brief: the approach, the areas to weigh, what "good" looks like. For a hard phase plan or a
   complex implementation, dispatch an **initial opus designer/reasoner** (clean context) instead of reasoning
   inline, so the direction is thought through without bloating your context. The orchestrator and an opus
   designer may write only the `.devx/` judgment artifacts described in §6, never product source.
2. **MAKE (sonnet).** A sonnet maker (designer / implementer / docs) executes the brief and **writes** the
   artifact.
3. **CHECK (opus, read-only, INDEPENDENT).** An initially clean checker lineage (reviewer / security) — **default sonnet; escalate to opus per §6** — judges the
   artifact against the **pre-committed acceptance criteria** — it must **not** see the PROPOSE rationale,
   or it is grading its own plan (the §8 independence rule). Same model, deliberately separate, ignorant
   contexts.
4. **FIX (sonnet).** A sonnet maker applies the check's findings in one pass (the correctness floor in
   `04-build` escalates if a blocking issue survives).

The **product-source maker is never opus**: `model_guard` permits opus only for
`reviewer`/`designer`/`security`, so it mechanically blocks opus for every product maker/plumbing role
(implementer/docs/git/scout and the rest). The designer exception is limited to `.devx/` judgment
artifacts; it does not make the designer a product-code writer. Opus's leverage is design/reasoning and
review, not implementation. **With no cost cap, be liberal escalating the CHECK/PROPOSE
roles (reviewer/security/designer) to opus on any non-trivial phase** — quality over cost; the workhorses
stay sonnet/haiku because a bigger model there doesn't move quality.

**CHECK applies to plans, not only code.** The PLAN is an artifact like any other, so it gets its own
CHECK before any MAKE consumes it (§6b). The same independence holds: the plan checker must **not** have
seen the PROPOSE/planning rationale, or it is grading its own plan.

---

## §6b — Independent plan-CHECK (before implementing a phase)

A plan can't be self-graded by the same context that produced it — independence (§8) covers **planning**,
not only code. Before the phase moves to MAKE/implement, run a plan-CHECK:

- **Who.** An initial clean-context agent that did **not** see the planning rationale. **Reuse an existing
  role — do not invent a new one.** Use a separate `devx:design:designer` running its **plan-CRITIC
  sub-behavior** (a second, independent designer lineage); it's in the `model_guard` opus allowlist, so
  escalate to opus per §6 for greenfield, GUI, architecture, security-critical, concurrency/device/hardware,
  or otherwise high-risk phases. Hand it the goal, roadmap, and the `phases/{NN}-{slug}/plan.md` — **not**
  the PROPOSE brief. (The reviewer stays a pure code-checker; the designer owns plan-CRITIC.)
- **What it challenges.** Per `references/contracts/plan-check.md` §P2 (dependency order + the inversion
  rule, missing prerequisites, weak/missing-negative-path criteria, oversized/overlapping tasks, missing
  interface decomposition, missing risk-tags / visual criteria, unlogged re-baseline, goal mismatch) — the
  canonical list; do not re-state it here.
- **Verdict.** ACCEPT or REVISE. A REVISE resumes the authoring designer for **one** revise loop, then
  resumes the producing critic to recheck under §2a. Use a fresh fallback if continuation is unavailable
  or the revision materially re-baselines scope/architecture/criteria. Escalate to the operator gate at
  stage 03 if a blocking concern survives the loop.
- **Log it.** `devx log DECISION orchestrator "phase {P} plan-check: {checker} → ACCEPT|REVISE ({why})"`.

This is the planning analogue of the §7 verify band: the planner can't self-approve. Cross-phase
dependency reconciliation (§6c) is part of what the plan-CHECK verifies.

---

## §6c — Cross-phase dependency reconciliation (at plan time)

**Canonical: `references/contracts/plan-check.md` §P4.** When the designer plans a phase, and the
plan-CHECK (§6b) reviews it, both reconcile the phase against the rest of the roadmap — not just the phase
in isolation:

- **Backward:** confirm every prerequisite this phase needs was actually delivered by a prior phase
  (read the prior `phases/*/summary.md`), not merely assumed.
- **Forward:** scan the remaining roadmap rows for anything that should be **stood up earlier** (a
  foundation a later feature depends on) or **deferred**.
- **The inversion rule:** a required foundation must **not** appear after the feature needing it unless
  that ordering is explicitly justified in the plan. A "needed in phase 2 but built in phase 5" inversion
  is a plan-CHECK finding, caught before code — not discovered at review. Reordering within the approved
  roadmap is autonomous (§7); anything that needs a new/expanded phase is a stage-03 gate.

---

## §7 — The per-phase loop (stage 04)

The build stage is a loop over the `roadmap.md` phases — each phase a full mini-lifecycle (full detail in
`stages/04-build.md`), applying the §6a triad at each step:

0. **Visual baseline for user-facing work** — if the product has UI, the first buildable slice must be a
   minimal visually satisfactory experience the operator can run and inspect. Do not defer all styling,
   layout, responsiveness, and interaction polish to late phases; later phases add capability on top of a
   working visual foundation.
1. **Plan the phase JIT** — opus directs; **designer** (sonnet) writes `phases/{NN}-{slug}/plan.md` from the goal,
   roadmap, and **all prior phase summaries**; dispatch **researcher**(s) (fan-out) for the phase's unknowns.
   Reconcile cross-phase dependencies (§6c) while planning.
1a. **Plan-CHECK (independent)** — run §6b: an initially clean **designer** lineage (plan-CRITIC sub-behavior) that did **not** see
   the planning rationale challenges the plan → ACCEPT or REVISE (one revise loop back to the designer).
   Implementation does not start on a plan that hasn't been ACCEPTed (or revised then accepted).
2. **Implement** — **implementer** (sonnet), following `agent-guide.md` §3 reuse-before-create discovery
   whenever the task creates a new code abstraction or dependency.
3. **Verify band (sequenced, each initial checker independent from the maker)** — run the verification
   **stages in order**, with only the stable-diff UI/security pair parallelized, so those checkers never
   audit code a pending functional review will rewrite:
   1. **Functional code review (3a)** — **reviewer** (functional + live-verify). Fix and re-review
      functional findings before continuing.
   2. **Stable-diff checks (3b)** — once 3a passes, run **ui:browser** (only if a UI changed) and
      **security** (full data-flow route) in parallel.
   3. **Consolidated 3b fix + regression** — apply the UI/security finding set once, resume the producing
      checkers, and resume the functional reviewer when the patch stays localized. Use a fresh regression
      reviewer only when §2a's broadened-scope fallback applies.
   4. **Durable-state update.**
   **Security may run earlier** (concurrent with or before code review) **only for a security-critical
   phase** with high early-design risk.
4. **Fix ×1 per verification return + re-verify** — resume the owning **implementer** for its current
   finding set when §2a permits, then **resume the producing checker or checkers** — never the
   orchestrator self-checking, so independence (§8) holds through the fix loop. Apply the
   **`[IMPORTANT]` rule** on every return: each `[IMPORTANT]`
   finding is **fixed**, **downgraded with evidence**, or **deliberately deferred with a reason + a
   backlog link** (`.devx/backlog.md`, §12) — never silently demoted or dropped; log the disposition as a
   `DECISION`. **Correctness floor:** a still-unmet criterion, a failing live-verify, a
   `REJECT`/surviving-`[BLOCKING]` review, or a surviving Critical/High vuln → **gate the operator** (never
   ship broken). One fix pass per verification return, then escalate.
5. **Document + summarize** — **docs** updates docs and writes `phases/{NN}-{slug}/summary.md` (the handoff that
   feeds the next phase's plan).
6. **Commit** — first confirm the **single status ledger** is consistent (§5): run
   `devx state check --workstream {slug}` and verify the durable artifacts agree (roadmap row · `state.md` ·
   `log.md` · `summary.md` · `review.md` · `security.md` · UI verdict · latest commit). A `status_drift`
   or any artifact disagreement **blocks the commit** — resolve it before the git agent runs. Then dispatch
   **git**, which **enforces the correctness floor as the sole committer**: it Reads the phase's `review.md`
   + `security.md` and **refuses to commit** per the commit gate in
   `references/contracts/phase-verification.md` §V4 (`REJECT` / unresolved `[BLOCKING]` / undispositioned
   `[IMPORTANT]` / surviving Critical/High) — surfacing the refusal instead. The single committer is the
   chokepoint that makes the floor stick — a failed-gate phase cannot be committed.
7. **Plan the next phase** — update `roadmap.md`, `devx index --scope project`, loop to step 1 for `P+1`;
   when the roadmap is done → `06-ship`.

**Termination is bounded by the operator-approved roadmap.** The roadmap is the loop's only stop
condition, so the loop may not grow it on its own: **adding a phase, or expanding a phase's scope
mid-loop, is a roadmap change → the operator gate (stage 03)**. Only reordering phases or *narrowing*
scope within the already-approved roadmap is autonomous. The loop may not silently extend its own stop
condition — that is how an autonomous run is guaranteed to terminate.

**Only the orchestrator assigns phase numbers**, drawn from the operator-approved `roadmap.md`. A
brainstorming or pre-roadmap **research spike lives OUTSIDE the numbered `phases/{NN}-*` tree** (e.g. under
the workstream's `research/` area) until the roadmap assigns it a number — an agent must never mint a
`phases/NN-*` directory for an un-roadmapped spike. The numbered phase tree mirrors the roadmap and
nothing else.

There is **no opus implementer and no 2-strike debug pass** — the bounded fix-pass rule plus the
correctness-floor escalation replace them (and keep opus read-only). Independence (§8) is absolute: the
verify-band checkers and the plan-CHECK (§6b) never see the planning rationale.

---

## §8 — Independence

Independence covers **PLANNING as well as code** — a plan cannot be self-graded by the lineage that
produced it, any more than code can be self-reviewed by the agent that wrote it. The plan-CHECK (§6b) is
the planning half of this rule: an initially separate checker that did **not** see the PROPOSE/planning
rationale judges the plan against the goal, roadmap, and acceptance criteria — not the planner's
self-justification. That checker may resume to evaluate the author's patch; it never becomes the author.

For code, the reviewer is always a separate lineage, initially clean, judging against criteria written
*before* the code (the plan's acceptance criteria / the failing tests). Resuming it for finding closure
preserves that boundary and saves remapping; a materially broadened patch gets a fresh regression checker
under §2a. Do not collapse implementer+reviewer to save a hop, and do not let the planner approve its own
plan.

The **`security:security`** agent shares this independence — a separate, read-only reviewer that *reports*
vulnerabilities (with `file:line` + fix) and never edits source; the implementer remediates. It runs
**per phase** as part of the verify band (full vuln categories + dependency audit + secret scan, traced
over the phase's data-flow route), and again as a **final whole-system pass at ship** (`06-ship`) for
cross-phase/integration issues. **Critical/High findings block** — they re-enter the fix step (or the
ship gate) before the work proceeds. Dispatch it at `opus` for a security-critical phase.

### §8a — Optional external second opinion

A different model can add useful independence, but another opinion is not another authority. Recommend the
Codex CLI path only for materially conflicting internal evidence, a security-critical/high-blast-radius
stabilized diff, or an operator request. Before **every** invocation, use `AskUserQuestion` with the reason,
scope, evidence paths, and output path; default to decline and log the decision.

When approved, follow `${CLAUDE_PLUGIN_ROOT}/tools-guide/native/codex-review.md` and invoke
`codex exec "prompt" -o output` inline in a read-only, ephemeral Codex run. The output is an untrusted
advisory artifact. Independently reproduce or disprove retained findings through the normal
reviewer/security/live-verification path; never auto-apply them, never substitute them for the correctness
floor, and never repeat the call merely to manufacture dissent.

---

## §9 — Git dispatch points

Dispatch the **git** agent to: create the workstream branch (00/03 boundary), commit each completed
phase after the verify band passes (04), and — **in remote VCS mode only** — push and open the PR at ship (06).

**VCS mode** (remote | local | none) is recorded in `project.md` and is **changeable at any time**.

- **Local is the default floor.** If the repo has no `.git`, dispatch `git op=init` + `op=setup` and
  work locally (branch + commits, no push/PR). No remote is required.
- **Remote is opt-in.** At attach the operator is **asked** whether to use a remote; declining keeps the
  mode local. Push and PR happen only in remote mode (§ ship). Switching local→remote later (at the ship
  gate or on explicit request) ensures/asks for a remote before proceeding.
- **none** (skip git entirely) still exists but is not the default.

Git manages the `.devx/` exclusion (`.gitignore` + `merge=union` for append-only logs). Destructive VCS
ops (force-push, reset --hard, branch -D) are **not in the git agent's allowlist**; if one is genuinely
needed, git surfaces it for an operator gate — never run autonomously.

---

## §10 — Decisions & scope

Record every direction/stack/architecture choice in `.devx/decisions.md` (append, dated). Any scope
change is an operator gate; on approval, have the designer (plan mode) update `goal.md`/`roadmap.md` and
the affected `phases/{NN}-{slug}/plan.md`, and log `DECISION`.

**Interruption protocol (a user interruption is a first-class direction change).** When the operator
interrupts mid-run with new input, do **not** silently fold it into the current task. Treat it like a
scope event:

1. **Restate** the understood change back to the operator in your own words (confirm via a gate if it is
   ambiguous or high-impact, §4).
2. **Identify affected phases/tasks** — which roadmap rows and in-flight `phases/{NN}-{slug}/` work the
   change touches.
3. **Decide whether scope or acceptance criteria changed.** If yes, it is an operator gate (stage 03) and a
   tracked re-baseline — record old → new → why, not a silent drift.
4. **Update durable artifacts** — `goal.md`/`roadmap.md`/affected `plan.md` via the designer (plan mode),
   `state.md` pointer, and log a `DECISION` in `log.md`. The change must survive a fresh-clone resume, not
   live only in chat.
5. **Revalidate impacted work** — re-run the §6b plan-CHECK on any re-planned phase and the relevant
   verify-band checkers (§7) on code the change invalidates; don't carry forward verdicts that predate it.

---

## §11 — Learnings distill & curation

Two compounding loops at document/ship time:

- **Distill (every workstream, no gate):** if `.devx/learnings.md` gained DevX/process entries, dispatch
  **docs** in *distill* mode to refresh `.devx/learnings-index.md` — clustering prompt, sequencing,
  tool-guidance, handoff, harness/plugin, and orchestration-resource failures into ranked, generalized
  **patterns** (+ `devx index --scope project`). This keeps DevX's project-local process corrections
  searchable instead of letting `learnings.md` rot into an append-only pile.
- **Curate (default-on, operator-gated):** at ship, offer vault promotion **by default** (the ship gate's
  curate question defaults to **yes**) so each workstream feeds its generalizable lessons **and durable
  per-phase research** back into the vault — the operator can decline. On yes, dispatch **docs** in
  *curate* mode — it promotes **only through the validation gate**
  (`devx validate .devx/cache/promote/{candidate}.md --promote-to {target}.md`:
  definitive-dead-link, provenance, collision, absolute-path-leak checks + a non-blocking
  dangling-link warning; writes +
  reindexes only on PASS). Operator-gated **and** code-gated, so the vault keeps improving with every
  shipped workstream while staying high-signal.
- **Stale references = drift (flag, never ignore):** if you or an agent hits a reference — a path,
  command, file, agent name, or doc link — that no longer resolves, treat it as drift, not noise. In the
  **target repo**, dispatch **docs** to fix it (the docs agent verifies cited paths/commands/symbols
  resolve and kills stale ones during the per-phase sync). For the **plugin itself**,
  `tests/test_plugin_refs.py` fails on any dangling intra-plugin reference (`${CLAUDE_PLUGIN_ROOT}`
  paths, `devx:<role>:<name>` dispatches, structural refs), so an edit can't silently introduce one. A
  reference that points at something that no longer exists is never "fine" — surface it and fix it.

---

## §12 — Backlog (the work queue)

`.devx/backlog.md` is a committed, human-editable plain markdown checklist of bugs, improvements, and
chores — the layer **above** workstreams. It is distinct from `log.md` (event trail), `state.md`
(current-workstream pointer), and plan phases (per-workstream task breakdown). The operator edits it
directly; you read and edit the file with Read/Edit.

**At attach** — Read `.devx/backlog.md`, surface open `- [ ]` items to the operator alongside any
existing workstreams, and let them pick what to work on.

**Starting an item** — when the operator picks an item, edit the checkbox to `- [~]` (in-progress) and
record the workstream slug on the same line or an indented note. Then create the workstream and run the
pipeline normally.

**Deferring a finding** — backlog entries created from `[IMPORTANT]` review/security/gui findings are not
generic reminders. They must include:
`source:{artifact finding-id}` · `prio:{high|med|low}` · `owner:{phase|workstream|human}` ·
`reason:{why not fixed now}` · `close:{observable condition}`. A vague "hardening later" entry is not a
valid disposition and the git commit gate treats it as undispositioned.

**At ship** — edit the checkbox to `- [x]` and append the result (PR URL / branch / handoff path) as
an indented note so the item is traceable.

The flow is: **`[ ]` open → `[~]` in-progress → `[x]` done with result link.**

**Environment preflight.** `devx doctor` is the env check that `/devx:devx-init` runs. If attach finds a
required tool missing, point the operator to `/devx:devx-init` rather than attempting to work around it.

---

## §13 — Risk → specialist (used within each phase)

The per-phase loop (§7, stage 04) already runs research at plan time (step 1) and the verify band
(reviewer + security + ui, step 3). This table is the reference for **which** specialist a given risk
needs — so you neither skip a needed one nor mechanically run all of them. Read each task's `Risk-tags:`
(set by the designer in plan mode) plus your own reading of the diff:

A specialist may surface work that warrants a **new phase or an expanded phase scope**. That is a
roadmap change (the loop's stop condition) → **gate the operator at stage 03** before adding it; do not
let a within-phase risk-dispatch silently grow the roadmap. Narrowing or reordering within the approved
roadmap stays autonomous (§7).

| Risk type | Signal introduced this phase | Specialist |
|---|---|---|
| research | new library/package; unverified platform/OS/device (ADB)/PDF/i18n behavior; packaging or licensing assumption | `devx:research:researcher` |
| security | subprocess/exec/eval; auth/authz change; secret/token handling; file I/O on untrusted paths; SQL; deserialization; SSRF; packaging | `devx:security:security` (opus if credential-handling/critical) |
| ui | any GUI widget/screen/layout changed; empty states; interaction or visual behavior | `devx:ui:browser` (web URL, or its desktop offscreen recipe for Qt/Electron/Tk) |
| platform | device detection; OS-specific calls; packaging (AppImage/deb/MSI/dmg) | `devx:research:researcher` |
| architecture | new module boundary / public interface / dependency-direction change | `devx:design:designer` (architect mode, refresh) |
| docs | any behavior-changing or user-visible feature, changed API or config | `devx:docs:docs` (incremental) |

Within each phase, log the dispatch decision — both DISPATCHED and SKIPPED are valid; a *silent* skip is the violation:
```bash
devx log DECISION orchestrator "phase {P} risk-dispatch: DISPATCHED {specialist} ({why}); SKIPPED {type} ({why})"
```
An empty `.devx/workstreams/{slug}/phases/{NN}-{slug}/research/` after a phase that introduced library/platform/packaging work is a warning — dispatch a researcher or log why not.
