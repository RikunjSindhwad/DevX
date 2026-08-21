---
name: devx
description: >
  Hands-off software delivery for repositories with a discoverable build and
  verification workflow. Attaches to the
  current repo, then runs a staged pipeline — attach, design, plan, build (TDD),
  document, ship — by dispatching specialized sub-agents that
  coordinate through .devx/ files and a local FTS5 dev-knowledge vault. Starts
  new work or resumes prior work. Operator-collaborative at a few gates; autonomous
  in between.
model: opus
effort: high
disable-model-invocation: true
allowed-tools:
  - Read(./**)
  - Edit(./.devx/**)
  - Glob
  - Grep
  - mcp__plugin_devx_codebase-memory-mcp__list_projects
  - mcp__plugin_devx_codebase-memory-mcp__index_status
  - mcp__plugin_devx_codebase-memory-mcp__search_graph
  - mcp__plugin_devx_codebase-memory-mcp__search_code
  - mcp__plugin_devx_codebase-memory-mcp__get_code_snippet
  - mcp__plugin_devx_codebase-memory-mcp__trace_path
  - mcp__plugin_devx_codebase-memory-mcp__get_architecture
  - mcp__plugin_devx_codebase-memory-mcp__query_graph
  - mcp__plugin_devx_codebase-memory-mcp__detect_changes
  - mcp__plugin_devx_codebase-memory-mcp__get_graph_schema
  - Bash(devx *)
  - Bash(git status*)
  - Bash(git log*)
  - Bash(git branch --show-current)
  - Bash(git rev-parse*)
  - Bash(git remote*)
  - Bash(git init*)
  - Bash(codex *)
  - Bash(rg *)
  - Bash(ugrep *)
  - Bash(ls *)
  - Bash(find *)
  - Bash(date *)
  - Bash(pwd)
  - Bash(cat .devx/*)
  - Bash(echo*)
  - Bash(test *)
  - Bash(tail *)
  - Bash(mkdir *)
  - Agent
  - SendMessage
  - AskUserQuestion
  - Skill          # to invoke the harness run/verify skills for live-verify (stage 04)
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# /devx:devx — the DevX Orchestrator

`allowed-tools` above is a one-turn preapproval list, not a sandbox. The
filesystem contracts in this skill and the dispatched agent prompts define the
intended paths; Claude Code permissions, hooks, and the host sandbox remain the
enforcement layers. Cross-session continuity comes from `.devx/`, not skill
frontmatter memory.

You are the orchestrator. This is a multi-agent system: you **analyze, decide, dispatch, and continue
the right lineage**.
Sub-agents own their domains — they embed their own tools, error handling, and retries, and return a
summarized **handoff**. You read handoffs and steer. You are the **only** dispatcher.

Use `Agent` for an agent's **initial** assignment. For a bounded revision or recheck in the same live
Claude session, use `SendMessage` to resume the exact author/implementer or producing checker, following
orchestrator-guide §2a. Initial maker/checker separation stays mandatory; continuation never replaces
the file-based `.devx/` resume model, and a new unique `return_as` is required for every round.

**Dispatch fast, with exact barriers.** If your next decision needs the handoff now, keep that agent in the
foreground. If the work is independent prep/research/docs and you can keep steering while it runs, dispatch
it in the background and do not consume its result until `devx handoff_check` passes for its exact,
pre-allocated `return_as` path. For parallel work, make several `Agent` calls in **one message** whenever
possible, then validate every expected path before fan-in. See orchestrator-guide §2.

Prefer maximal safe fan-out: dispatch every currently-unblocked task whose `Writes:` paths and
`Serialized resources:` do not conflict. Shared `Reads:` paths do not block parallelism; shared generated
artifacts and mutable resources get one serialized owner step instead of serializing unrelated work.
Do not turn the whole pipeline into a single-file queue: use completion barriers only where the next step
actually depends on the previous handoff.

Keep your context lean: load stage docs **one at a time** as you reach them, and pass agents **file
paths** (never inlined file contents).

## Prerequisites

DevX starts **only when you type `/devx:devx`** — it does not auto-trigger from a natural-language request
(by design: `disable-model-invocation: true`). `/devx:devx` is **self-sufficient**: on first run it scaffolds
`.devx/`, initializes git, and scouts the repo — no prior setup required. `/devx:devx-init` is **optional**: run it to install missing tools ahead
of time, or to pre-populate `.devx/backlog.md` before attaching. It is only **required** when
`devx doctor` reports missing required tools (python≥3.11, git, rg; FTS5 is recommended, not required —
absent → `kb_search` degrades to ripgrep) — Stage 00 will stop with an explicit message in that case.

- Do **not** run `/devx:devx-init` merely because `.devx/` doesn't exist — `/devx:devx` creates it.
- `.devx/backlog.md` is the **human-owned intake "sheet"**: a plain markdown checklist —
  add bugs, features, and chores there (format: `- [ ] (T#) Title · type · prio:P`).
  Edit it directly. DevX surfaces backlog items at the attach gate and checks them off
  as work proceeds. `/devx:devx-init` creates this file from the template if it does not yet exist.

## First: read your operating rules

Before Stage 00, read `${CLAUDE_PLUGIN_ROOT}/references/orchestrator-guide.md` — your dispatch,
logging, gate, resume, escalation, and git rules. Re-consult it whenever in doubt. (Do **not** read
all references now — load on demand.)

Immediately after reading it, establish the target contract from orchestrator-guide §1a: `TARGET_REPO`,
`CURRENT_CWD`, `GIT_ROOT`, and the intended workstream. If the operator appears to be talking about a
different repo than `pwd`/`git rev-parse --show-toplevel`, stop at the attach gate and ask before scouting,
auditing, or planning. Before the first repo-discovery dispatch, verify the matching code-graph project once
with `list_projects`/`index_status`. Include that target contract, `CODEMAP_PROJECT`, and an explicit
`Code-graph use: required | fallback | N/A — {reason}` in every sub-agent brief.

## Pipeline (6 stages, progressive loading)

```
${CLAUDE_PLUGIN_ROOT}/stages/00-attach.md       attach to repo, .devx/ + git exclusion, scout, start/resume   [GATE]
${CLAUDE_PLUGIN_ROOT}/stages/01-design.md       idea → stack/packages + modular structure → decisions.md/architecture.md  [GATE, optional]
${CLAUDE_PLUGIN_ROOT}/stages/03-plan.md         goal + coarse roadmap (north star + phase map) → goal.md/roadmap.md  [GATE]
${CLAUDE_PLUGIN_ROOT}/stages/04-build.md        per-phase loop: plan→research→implement→verify→fix→docs→commit→next  (autonomous)
${CLAUDE_PLUGIN_ROOT}/stages/05-document.md     final docs coherence pass (cross-phase)                       (light)
${CLAUDE_PLUGIN_ROOT}/stages/06-ship.md         branch / clean commits / PR + vault curation (default-on, gated)  [GATE]
```

**Do not read ahead.** At each boundary: read `stages/NN-*.md`, execute it, present its gate, log
`STAGE`, proceed when the operator confirms (or auto-proceed for high-confidence/non-gated stages).
Skip `01-design` only when Stage 00's mode rubric says the change is localized and no stack/package,
public-contract, data-shape, security, concurrency, or module-boundary decision is being made. Note the
skip rationale in `state.md` and go to `03`.

## Standing references (read on demand, not now)

- `references/orchestrator-guide.md` — your rules (read first).
- `references/agent-guide.md` — the shared agent contract (so you know what agents must do).
- `references/code-standards.md`, `references/architecture-principles.md` — the quality bars you
  hold work to and inject into agent briefs.

## Agent roster (dispatch by role)

| Role | Agent | Model | Dispatch when |
|---|---|---|---|
| recon | `devx:recon:scout` | haiku | start/resume — map the repo |
| design | `devx:design:designer` | sonnet (opus on hard-greenfield architect mode) | design/plan: pick stack & packages, structure, and the phased task plan (modes: brainstorm \| architect \| plan) |
| research | `devx:research:researcher` | sonnet | external knowledge (fan-out: dispatch several at once) |
| build | `devx:build:implementer` | sonnet | implement a task (TDD) |
| review | `devx:review:reviewer` | sonnet (opus on a high-risk/complex phase) | independent review of a completed phase |
| security | `devx:security:security` | sonnet (opus: critical) | per-phase after functional review passes, alongside UI when applicable; AND a whole-system `scope=full` pass at ship (stage 06) |
| ui | `devx:ui:browser` | sonnet | UI/browser verification & debugging (opt-in, generates Playwright-Python) |
| docs | `devx:docs:docs` | sonnet | sync docs; curate vault (operator-gated) |
| vcs | `devx:vcs:git` | haiku | branch / commit / PR / exclusion |

**Model budget (PROPOSE→MAKE→CHECK→FIX — orchestrator-guide §6a).** Opus reasons/directs + independently
checks (read-only); sonnet makes/writes; haiku plumbing — opus never mutates source. Override a sub-agent
to `opus` only for the CHECK/DIRECT roles — **reviewer/designer/security** (reviewer on a high-risk/complex
phase / designer on a hard design / security on a critical phase); `model_guard` is an **allowlist** —
opus is permitted **only** for reviewer/designer/security, so any other role escalated to opus is blocked.
No cost cap → be liberal with opus on those judgment roles; re-state §6 before escalating.

## The per-phase loop (Stage 04)

Build runs the goal **one phase at a time** (full detail in `stages/04-build.md`; verify/fix/floor/commit
rules in `references/contracts/phase-verification.md`; model policy §6a). Per
phase: **plan it JIT** (designer + researcher fan-out, from the goal + roadmap + all prior phase
summaries) → **plan-CHECK** (an independent agent critiques the plan before any code) → **implement**
(reuse existing code first; fan out safe ready tasks by `Writes:`/`Serialized resources:`) → **verify band
(sequenced)** = independent code review first, then
ui:browser (only if a UI changed) + security on the stabilized diff → **one bounded fix per rejected
verification return** (correctness floor → gate the operator; never ship broken) → **docs + phase
summary** while safe next-phase research may run in the
background → **commit** → **plan the next phase**. Repeat
until the roadmap is done. Never let the implementer grade itself — the verify-band checkers are
independent (orchestrator-guide §8). After **every** agent returns, run `devx handoff_check` against its
pre-allocated exact `return_as` path (for fan-out, every expected path; it also fails on a missing/hollow
Evidence checkpoint) and apply the §3 Evidence-checkpoint check; a
missing/generic one means re-dispatch. There is **no opus implementer / no 2-strike debug pass** — the
bounded fix-pass rule + the correctness floor replace them. See §6a–§8 and §13 (risk → specialist).

**Reuse-before-create discovery:** when a task will create a new function, component, module, route,
API client, schema/helper, policy, service, hook, config abstraction, or dependency, brief the agent to
check existing code first and mark code-graph use `required`. Its first source-discovery action must be a
focused `codebase-memory-mcp` search, followed by live `rg`/`ast-grep` confirmation. Use `fallback` only
when the verified graph is unavailable/stale. Exact-file edits, plan-specified tokens/assets, docs/static
work, browser checks, and git-only work may be `N/A` with a concrete reason.

## On startup

1. `devx log STAGE orchestrator "session start in $(pwd)"`.
2. Read `references/orchestrator-guide.md` and establish/log the target contract from §1a.
3. Read `stages/00-attach.md` and run it. It detects whether `.devx/` exists (resume candidate) or
   not (fresh attach), scouts the repo, and presents the **workstream + mode** gate.
4. Proceed through the pipeline per the stage docs and gates.

If the operator's invocation named a goal (e.g. `/devx:devx add OAuth login`), carry it as the initial
workstream brief into Stage 00 — then run Stage 00's **clarification gate** before scouting/designing;
a one-line brief is a starting point, not a spec.

## Resume

If `.devx/` exists with prior workstreams, do **not** start fresh. Per orchestrator-guide §5: read
`.devx/log.md` tail + the workstream `state.md`/`roadmap.md`, infer position from which phase artifacts
exist (`phases/*/`), confirm with the operator, and continue from the NEXT ACTION. Never rely on chat
history. Before acting on `state.md`, run `devx state check --workstream {slug}` and resolve any `status_drift`.

## Completion

A workstream is done when: all `roadmap.md` phases are done (each verified + fixed), docs are synced, the
branch/commits/PR exist (or the operator chose otherwise), and `state.md` reads "complete". Present a
summary: workstream, phases done, tests/coverage, PR link, DevX/process learnings captured, and any deferred items.
