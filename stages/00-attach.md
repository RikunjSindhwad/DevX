# Stage 00 — Attach

## Objective
Attach DevX to the current repo (CWD): create or locate `.devx/`, make it shared-but-tidy in git, scout
the repo, choose a workstream, and decide whether this is a fresh start or a resume. End with the
**workstream + mode** gate.

## Steps

### 0. Environment preflight
Run `devx doctor`. If it exits non-zero (a required tool is missing), **stop** and tell the operator:
```
Environment not ready. Run /devx:devx-init first to install missing tools.
Missing: {missing_required from devx doctor JSON}
Hints:   {install_hints from devx doctor JSON}
```
A missing `.devx/` is **normal** — `/devx:devx` scaffolds it below. Do NOT route to `/devx:devx-init` merely
because `.devx/` doesn't exist. Do NOT attempt to install anything here — `/devx:devx-init` owns tool
installation.

### 1. Precheck (read-only — no writes yet)
```bash
pwd
git rev-parse --is-inside-work-tree 2>/dev/null
git remote -v 2>/dev/null
ls -1 .devx/workstreams 2>/dev/null
tail -n 5 .devx/log.md 2>/dev/null
```
(The orchestrator reads these outputs directly; an error or empty result means "not present".)

**Establish the VCS mode** — detect git state, then confirm with the operator (AskUserQuestion). Local
is the **default floor**; none is never the default.

- **If no `.git` in CWD:** DevX will initialize a local git repo (plan to dispatch
  `devx:vcs:git op=init` then `op=setup`). Then ask (AskUserQuestion):
  ```
  "No git repo found. DevX will initialize a local git repo. Do you also want to work with a
   remote (push + PRs) — for example, GitHub?"
     - Yes, set up a remote too  →  remote mode (you'll supply the URL or we'll create it)
     - No, local commits only    →  local mode  [default]
  ```
  If the operator declines → stay **local**.

- **If `.git` exists and a remote is configured:** default is **remote**. Confirm:
  ```
  "Found git repo with remote {url}. VCS mode: remote (push + PRs)?"
     - Yes, remote  [default]
     - Local only — keep commits, no push/PR
     - None — skip git entirely
  ```

- **If `.git` exists but no remote:** default is **local**. Confirm:
  ```
  "Found local git repo (no remote configured). VCS mode: local (commits only)?"
     - Yes, local  [default]
     - Add a remote and use remote mode
     - None — skip git entirely
  ```

Record the choice in `.devx/project.md` as:
- `VCS mode: local`
- `VCS mode: remote (origin: {url})`
- `VCS mode: none`

State explicitly in `project.md` that **the mode is changeable anytime** — the operator can switch
local → remote (or back) later; the ship gate and any explicit operator request can change it. It
governs Stage 06: **remote** pushes + opens a PR; **local** stops at clean commits on the branch;
**none** skips git entirely.

### 2. Resume vs fresh (gate) — with backlog intake
Check for an existing backlog: Read `.devx/backlog.md` directly (it is a plain markdown checklist).
Collect all open `- [ ]` items and surface up to 3 alongside the other options below.

Branch on **whether `.devx/workstreams/` contains one or more workstreams** — not on whether `.devx/`
itself exists (it may have been created by `/devx:devx-init` with only `project.md` / `backlog.md`).

- **`.devx/workstreams/` has one or more workstreams** → this is a **resume candidate**. Per
  orchestrator-guide §5, read each workstream's `state.md` (NEXT ACTION) and which `handoffs/` exist.
  Present (AskUserQuestion):
  ```
  "Found prior DevX state. What now?"
    - Resume "{slug}" (at: {NEXT ACTION})
    - Start a new workstream
    - Work the next backlog item — "{text}"  [shown only when open items exist; list up to 3]
    - Review prior state first
  ```
  On **resume**: skip to the stage named by NEXT ACTION (do NOT re-run scout/design unless stale).
  If the operator's resume request is itself an **update/change** to the existing workstream (new
  behavior, scope delta, a "now also do X"), run the **clarification gate** below before re-planning
  — re-confirm intent, the **scope delta**, and explicitly **what must NOT change** — then route the
  delta through the appropriate stage (a goal/scope change returns to the stage-03 gate; a contained
  change re-enters stage 04). Record the clarified delta into `brief.md`.
  On **work the next backlog item**: use the item's text as the workstream goal, then Edit
  `.devx/backlog.md` to mark the item in-progress by flipping its `- [ ]` to `- [~]` (the in-progress
  marker per orchestrator-guide §12 — `[ ] → [~] → [x]`; not an HTML comment), e.g.
  `- [~] {item text} <!-- {slug} -->`, as part of spinning up the workstream in step 4.

- **No workstreams yet** (whether `.devx/` is absent OR exists from `/devx:devx-init` with only
  `project.md`/`backlog.md`) → **fresh workstream selection**. If `.devx/backlog.md` has open `- [ ]`
  items, offer (AskUserQuestion):
  ```
  "How would you like to start?"
    - Work the next backlog item — "{text}"  [up to 3 shown]
    - Start a new workstream (describe your goal)
  ```
  On **work the next backlog item**: Edit `.devx/backlog.md` to flip the item's `- [ ]` to `- [~]`
  (in-progress, per §12) when the workstream is created in step 4. Continue to scaffold.

> **Mid-run interruptions.** If the operator interrupts an in-flight run with a new request, capture it
> as a lightweight artifact before resuming: **request → interpretation → affected phases/criteria →
> revalidation needed**. Run the clarification gate (step 4b) on the interruption the same way — restate
> the understood change and confirm it. If the change altered scope or acceptance criteria, **re-plan**
> the affected phases (a goal/scope change returns to the stage-03 gate) and revalidate impacted work;
> if it didn't, note the interpretation and resume. Append the capture to `state.md`/`brief.md` so the
> delta is traceable, never a silent course-correction.

### 3. Scaffold `.devx/` (idempotent — create any missing files; never overwrite existing ones)
Create any **missing** workspace files (skip files that already exist — `/devx:devx-init` may have created
them):
```
.devx/{log.md, decisions.md, learnings.md, project.md}   # project.md is filled by scout, or by the greenfield baseline below
.devx/workstreams/
```
Do **not** overwrite an existing `project.md` or `backlog.md`; seed only what is absent. Then dispatch
**git** `op=setup` so `.devx/cache/` and `.devx/index/` (transient cache + derived FTS index) are
git-ignored and `log.md`/`learnings.md` are `merge=union` (shared state, branch-merge-safe).
`devx log STAGE orchestrator "attach: scaffolded .devx"`.

### 4. Define the workstream
Derive a slug from the operator's goal (e.g. `/devx:devx add OAuth login` → `oauth-login`). If no goal was
given, ask for one (AskUserQuestion). Create `.devx/workstreams/{slug}/{brief.md, state.md}` and
`handoffs/` (the 6-section handoffs live there). Reviews are phase-scoped and land under
`phases/{NN}-{slug}/`. Research for an assigned phase lands in that phase; a pre-roadmap/brainstorm spike
may use the non-numbered `.devx/workstreams/{slug}/research/` area. Never invent a numbered phase for a
spike. Write `brief.md` (what + why) and `state.md` (NEXT ACTION = "scout").

### 4b. Clarification gate (before scouting/designing a fresh or thin brief)
A fresh, thin, or ambiguous brief must be **clarified before any scout/design runs** — building from a
half-understood goal is the most expensive mistake in the loop. Skip only when the brief is already
concrete and unambiguous (e.g. a precise quick-fix). When in doubt, run the gate; one round of
questions is cheaper than a wrong build.

The orchestrator (only the orchestrator owns `AskUserQuestion`) runs a **structured** gate that
confirms, at minimum:
- **Concrete outcome** — the specific thing that should exist when this is done.
- **What "done" means** — the observable success condition the operator will check.
- **Target users & primary workflows** — who uses it and the main paths they take.
- **Platform / runtime constraints** — OS, runtime, framework, deployment target, versions.
- **Security / data sensitivity** — secrets, PII, auth, untrusted/forensic input, network/subprocess.
- **Explicit non-goals** — what is deliberately out of scope.
- **Acceptable tradeoffs** — speed vs. polish, scope vs. time, what may be cut under pressure.
- **Autonomous-vs-staged-approval preference** — run end-to-end, or pause at phase/scope boundaries.

Frame each question to **surface misunderstanding**, not to rubber-stamp — state your reading and ask
the operator to correct it: *"I read this as X — is it X, or did you mean Y?"* Prefer presenting your
interpretation as one option against a plausible alternative so a wrong assumption gets caught here,
not in code. Group related items so the gate is a few focused questions, not an interrogation.

**Record the answers into `brief.md`** (and any hard constraints worth durable status into
`project.md` / `decisions.md`) so the designer plans from a **clarified spec**, not the raw one-liner.
`devx log GATE orchestrator "clarification recorded: {slug}"`.

### 5. Scout the repo — or write a greenfield baseline
First determine whether the repo has meaningful app/source files yet: manifests (`package.json`,
`pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle*`, `*.sln`, etc.), source dirs, or
test/build config. A newly initialized empty repo is not something to "scout" as if implementation
already exists.

- **Meaningful repo exists** → dispatch **scout** (haiku). It writes/refreshes `.devx/project.md`
  (stack, layout, test/build/run commands, conventions). Read its handoff (paths, not contents).
- **Greenfield-empty repo** → do **not** dispatch full scout yet. Write a short `.devx/project.md`
  baseline from the clarified brief and attach choices:
  - `scout_status: greenfield-empty`
  - intended platform/runtime constraints from `brief.md`
  - `VCS mode: ...`
  - `Run/live verification: TBD until scaffold`
  - `Quality gate: TBD until scaffold`
  - `Re-scout after scaffold: required`
  Then route through design/roadmap normally. After the first scaffold phase lands real manifests and
  run/test commands, dispatch scout to replace the baseline with a real map before later feature phases.

For Linux multi-service/multi-package repos, if `docker-compose.yml`, `docker-compose.yaml`,
`compose.yml`, or `compose.yaml` exists, scout/baseline must record whether `docker compose` is the
preferred live verification stack (web/api/db together). Prefer compose for browser/API/DB live
verification unless the operator or `project.md` says host processes are the intended run model.

Then `devx index --scope project` so `project.md` (and any prior decisions/learnings/research) is
searchable via `kb_search --scope project`.

### 6. Choose the path (greenfield vs brownfield)
From scout's map + the brief, decide which stages run:

**greenfield / new subsystem** — run `01-design → 03 → 04 → 05 → 06`.
Use when the work creates a new app/service/module, public API, data model,
persistence/auth/security boundary, runtime/framework/package choice, or unclear stack direction.
Do not use when the change is purely local and the architecture already answers where it belongs.

**brownfield feature/change** — run `03 → 04 → 05 → 06`.
Use for an existing codebase with a known stack when the work changes behavior across multiple files or
needs task decomposition/review. If it adds a new framework/package or changes module boundaries, run
`01-design` first.

**quick-fix** — run minimal `03 → 04 → 06`.
Use only for one localized bug/chore with no new dependency, no public contract/data-shape change, no
architecture boundary touched, and obvious tests. Any uncertainty about package choice, ownership,
blast radius, or acceptance criteria pushes the work to brownfield or greenfield.

Creative shortcuts are allowed only when they preserve the reasoning contract. If skipping 01-design, write one
sentence in `state.md` explaining why the skip is safe. When uncertain, run the stage; the cost of one
planning/design pass is lower than a vague build loop.

## User Gate
Present and wait (AskUserQuestion):
```
Attached to {repo} ({stack from project.md}).
Workstream: {slug} — {one-line brief}
Mode: {greenfield | brownfield | quick-fix}; stages: {list}
VCS: {remote (origin: {url}) | local | none}   ← changeable anytime
Backlog item: {text, or "none"}
Proceed?
```
Log the answer: `devx log GATE orchestrator "attach approved: {slug}, mode {…}"`.

## Verification
- `devx doctor` exited zero (or the operator was sent to `/devx:devx-init` and we restarted clean).
- `.devx/` exists with `log.md`, `decisions.md`, `learnings.md`, `project.md`, and the workstream dir.
- `project.md` names the **real** test/build commands (scout verified them), or explicitly says
  `scout_status: greenfield-empty` with `Re-scout after scaffold: required`.
- On Linux, if compose files exist, `project.md` records whether live verification uses
  `docker compose` or why host processes are preferred.
- git `op=setup` ran (`.gitignore` has `.devx/cache/` + `.devx/index/`; `.gitattributes` has the
  union-merge lines) — or the operator chose no-VCS.
- `state.md` has a concrete NEXT ACTION.
- `project.md` records the **VCS mode** (remote (origin: {url}) | local | none) the operator chose,
  plus the note that the mode is changeable anytime.
- If a backlog item was selected, `.devx/backlog.md` was edited to mark the item `- [~]` (in-progress).

## Output artifacts
`.devx/{log.md, decisions.md, learnings.md, project.md}`, `.devx/workstreams/{slug}/{brief.md, state.md,
handoffs/}`, `.gitignore` + `.gitattributes` updates, scout's handoff.

## Next
Read `stages/{the first stage in the chosen path}.md`. Do not read ahead.
