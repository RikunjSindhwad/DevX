---
name: devx-init
model: sonnet
description: >
  One-time (idempotent) bootstrap that makes an existing project ready for DevX.
  Checks and installs missing required/optional tools, ensures a local git repo,
  builds the FTS5 vault index, verifies the code graph MCP, scaffolds .devx/ with project.md and
  a backlog "sheet", then hands off to /devx:devx to attach, choose a VCS mode, and
  start work. Safe to re-run: skips present tools, rebuilds indexes, never clobbers
  existing .devx/ content.
disable-model-invocation: true
allowed-tools:
  - Read(./**)
  - Glob
  - Grep
  - mcp__plugin_devx_codebase-memory-mcp__index_repository
  - mcp__plugin_devx_codebase-memory-mcp__list_projects
  - mcp__plugin_devx_codebase-memory-mcp__index_status
  - mcp__plugin_devx_codebase-memory-mcp__search_graph
  - mcp__plugin_devx_codebase-memory-mcp__search_code
  - mcp__plugin_devx_codebase-memory-mcp__get_code_snippet
  - mcp__plugin_devx_codebase-memory-mcp__get_architecture
  - Bash(devx *)
  - Bash(git status*)
  - Bash(git remote*)
  - Bash(git rev-parse*)
  - Bash(git init*)
  - Bash(python3*)
  - Bash(pip*)
  - Bash(${CLAUDE_SKILL_DIR}/../../bin/install-codebase-memory-mcp*)
  - Bash(rg *)
  - Bash(ls *)
  - Bash(find *)
  - AskUserQuestion
  - Bash(sudo apt-get*)
  - Bash(brew*)
  - Bash(sudo dnf*)
  - Bash(sudo pacman*)
  - Bash(sudo zypper*)
  - Bash(sudo apk*)
---

# /devx:devx-init — Bootstrap a Repo for DevX

`allowed-tools` preapproves matching calls for the invocation turn; it does not
restrict unlisted tools. This skill still writes only the explicitly described
`.devx/` bootstrap files and asks before installs or privileged changes.

You are the **one-time bootstrapper**. Your job is to get the environment and repo
ready for `/devx:devx` to attach cleanly. You do NOT plan, build, or dispatch any
pipeline agents. You do NOT ask about the operator's workstream goal — that is
`/devx:devx`'s job at the attach gate.

This skill is **idempotent**: re-running it is always safe. It skips tools already
present, rebuilds indexes from scratch (cheap, correct), and never overwrites
existing `.devx/` content.

---

## Procedure

### Step 0 — Confirm target cwd

Run `pwd` and `git rev-parse --show-toplevel 2>/dev/null` before `devx doctor`. If the operator named a
different repo than the live cwd/git root, stop and ask which directory to bootstrap. `/devx:devx-init` writes
`.devx/` in the current repo; running it in the wrong chat/cwd pollutes the wrong project.

### Step 1 — Preflight: run `devx doctor`

```bash
devx doctor
```

Parse the JSON output. Present a checks table to the operator:

| Tool | Status | Required? | Why |
|------|--------|-----------|-----|
| …    | …      | …         | …   |

Also surface the detected **package manager** (from the `package_manager` field).

If `ok` is `true` and no `.devx/` exists, continue. If `ok` is `true` and `.devx/`
already exists, continue (idempotent — indexes and backlog will still be refreshed).

---

### Step 2 — Install missing tools (CHECK, THEN CONFIRM)

Split the report into **required blockers** and **optional accelerators**. For each missing required tool,
show the exact install command from the `install` field in the doctor JSON. For each absent optional tool,
show what degrades if skipped:

| Optional tool | If skipped |
|---|---|
| `codebase-memory-mcp` | Agents fall back to live `rg`/`ast-grep`; duplicate/reuse discovery is weaker and less structured. |
| `ast-grep` | Structural searches fall back to text `rg`; acceptable but less precise. |
| `ugrep` | Long-line/minified searches fall back to `rg`; acceptable unless this repo has bundles. |
| `gh` | PR creation and GitHub code search are unavailable; local work still runs. |
| Playwright + Chromium | Web UI verification is unavailable; the browser agent returns `SETUP_REQUIRED` instead of modifying the operator-owned runtime. |

Ask the operator (AskUserQuestion):

> "The following tools are missing. How would you like to proceed?"
>
> Options:
> - Install required blockers now; skip optional accelerators for now  [recommended]
> - Install required + selected optional tools
> - I'll run them myself — show me the commands

**NEVER run `sudo …` without this explicit confirmation.** User-space installs
(e.g. `pip install …` into a venv) are safe to run directly once confirmed.

For `codebase-memory-mcp`, prefer the plugin installer after confirmation:
```
${CLAUDE_PLUGIN_ROOT}/bin/install-codebase-memory-mcp
```
It downloads the latest release asset from GitHub, verifies it against the release `checksums.txt`, and
installs to `~/.local/bin/codebase-memory-mcp`. If the operator wants a different path, pass it as the
first argument or set `CODEBASE_MEMORY_MCP_BIN` to the installed binary.

On any install choice:
1. Run each install command in order.
2. If a command fails due to permissions (exit 2 / "Permission denied"), do NOT
   retry silently. Tell the operator: "Run this in your terminal with `! <command>`
   (the `!` prefix passes it directly to your shell session)."
3. After installs, re-run `devx doctor` to verify the required tools are now present before continuing.
   Optional tools may remain degraded; surface that plainly, but do not block.

**Workspace env (uv) — optional:** the runtime is stdlib-only, so no env is needed to attach and work.
Create one only if the operator wants to run DevX's own test suite or the richer fetch tiers. Use **uv**
(nothing touches system Python) and put it in the DevX workspace — `.devx/.venv`, never the repo root:
```
uv venv .devx/.venv
uv pip install --python .devx/.venv/bin/python -r ${CLAUDE_PLUGIN_ROOT}/requirements-dev.txt   # dev/test
uv pip install --python .devx/.venv/bin/python requests trafilatura beautifulsoup4              # optional fetch tiers
```
`bin/devx` auto-uses `.devx/.venv` when present (else uv's isolated run, else stdlib `python3`). Offer it;
do not force it. (If `uv` is missing, `devx doctor` reports it with an install command.)

**Browser verification runtime (optional, operator-owned):** when the operator expects web UI work, offer
Playwright during the same confirmed setup step. Create/reuse `.devx/.venv` as above, then run:
```
uv pip install --python .devx/.venv/bin/python playwright
.devx/.venv/bin/python -m playwright install chromium
```
This is the only DevX workflow that provisions the browser/helper runtime. Role agents only preflight and
consume it; if absent they return `SETUP_REQUIRED` to the orchestrator.

---

### Step 3 — Ensure a local git repo

```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

- If the command exits non-zero (no `.git`): run `git init` directly via
  `Bash(git init*)`. DevX's default floor is a **local** git repo. This is a bare
  init only — no further git configuration is done here.
- If `.git` already exists: nothing to do; continue.

**`.devx/` git-exclusion is deferred.** Adding `.devx/cache/` and `.devx/index/`
to `.gitignore`/`.gitattributes`, and setting `merge=union` on log files, is Stage
00's job: `/devx:devx` dispatches `git op=setup` once a workstream exists. Do NOT
attempt git exclusion setup here — the `vcs:git` agent requires a workstream that
doesn't exist during bootstrap.

**Do NOT ask about remotes here.** The remote-vs-local choice is the VCS-mode gate
inside `/devx:devx` Stage 00. Just note: "Remote / push / PR setup happens at the
`/devx:devx` attach gate."

---

### Step 4 — Build indexes

```bash
devx index
```

Run unconditionally. It is fast and idempotent. `devx index` builds the FTS5 vault
so `kb_search` works.

If `codebase-memory-mcp` is installed, do not pre-index here unless the operator asks. The MCP graph is
per target repo and can be large; agents index or refresh it when code discovery is needed. Ensure the
project has a `.cbmignore` if non-product directories would pollute source discovery:
```
.devx/
.codebase-memory/
node_modules/
dist/
build/
coverage/
.turbo/
.next/
```

---

### Step 5 — Scaffold `.devx/`

1. **Create the directory** if it does not exist: `mkdir -p .devx/`.

2. **`project.md`:**
   - If `.devx/project.md` already exists, leave it untouched.
   - If it does not exist: write a minimal stub directly (Write tool):
     ```
     # Project
     <!-- Filled by /devx:devx at attach (Stage 00 scout). -->
     Stack:
     Layout:
     Test command:
     Build command:
     Run command:
     VCS mode: (set at /devx:devx attach)
     ```
     Do NOT dispatch `devx:recon:scout` here. The scout sub-agent requires a
     workstream that doesn't exist during bootstrap. Stage 00 of `/devx:devx` dispatches
     the scout and fills in the real content.

3. **`backlog.md`:**
   - If `.devx/backlog.md` already exists, leave it untouched.
   - If it does not exist: copy `${CLAUDE_PLUGIN_ROOT}/templates/backlog.template.md`
     to `.devx/backlog.md`. This creates the human-owned intake "sheet" the operator
     can fill with bugs and improvements for DevX to work on.

4. **Empty files (create-if-absent, never clobber):** `log.md`, `decisions.md`,
   `learnings.md` — create each as an empty file if it does not exist.

---

### Step 6 — Verify and report

Re-run `devx doctor` one final time. Print a concise summary:

```
Bootstrap complete
==================
Environment : READY  (or: NOT READY — see below)
Git         : local repo present (bare init only — git exclusion deferred to /devx:devx Stage 00)
Indexes     : vault index built
Code graph  : codebase-memory-mcp ready (or: missing — agents will fall back to rg/ast-grep)
.devx/      : scaffolded (project.md stub, backlog.md, log.md, decisions.md, learnings.md)

Missing (if any):
  - <tool>: <why> — install with: <command>

Next step
---------
Run /devx:devx to attach. It will set up git exclusion (.devx/ ignored, merge=union on
log files), run the repo scout (filling project.md), choose your VCS mode (local
by default; remote opt-in), and start or pick a backlog item from .devx/backlog.md.
```

If any **required** tool is still missing, show the install hint and tell the
operator to re-run `/devx:devx-init` after installing it. Do NOT proceed to `/devx:devx`
automatically — the operator must confirm their environment is ready.

**FTS5 absent** is a DEGRADED warning, not a blocker. `devx doctor` exits non-zero
only when a REQUIRED tool is missing; FTS5 absence degrades retrieval to ripgrep
fallback but does not block bootstrap. Surface it in the summary table, but do not
treat it as a failure.

---

## Notes

- **Idempotent**: safe to re-run at any time. Present tools are skipped. Indexes
  are rebuilt. Existing `.devx/` content is never clobbered.
- **Scope**: this skill bootstraps the environment and repo floor only. Workstream
  goals, VCS mode, design, plan, and build all belong to `/devx:devx`.
- **Non-agentic**: `/devx:devx-init` does NOT dispatch sub-agents. All steps are
  performed directly (Bash, Write, Read). Sub-agents (`vcs:git`, `recon:scout`,
  etc.) require a workstream that doesn't exist during bootstrap. The `/devx:devx`
  orchestrator is the only dispatcher — it creates the workstream in Stage 00 and
  dispatches agents from there.
- **What `/devx:devx` does that `/devx:devx-init` does not**: git exclusion setup (`op=setup`
  via `vcs:git`), repo scouting (fills `project.md` via `recon:scout`), VCS-mode
  selection, and workstream creation. Run `/devx:devx` after bootstrap to get all of
  that.
