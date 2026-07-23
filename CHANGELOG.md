# Changelog

All notable changes to **DevExpert** are documented here.
This project adheres to [Semantic Versioning](https://semver.org).

## 1.0.0 — Initial release · 2026-07-23

The first public release of **DevExpert** — a file-native, graph-engineered SDLC
for Claude Code. Hand it a goal; an Opus orchestrator plans, builds, reviews,
documents, and ships through a graph of specialized agents, while you gate only
direction, scope, and release.

### Delivery pipeline
- **6-stage pipeline** (`attach → design → plan → build → document → ship`) loaded
  progressively, with operator gates on goal/scope and ship; the build stage runs
  fully autonomously between them.
- **Autonomous per-phase build loop** — just-in-time planning, an **independent
  plan-CHECK** (the planner can't self-approve), test-first / reuse-first
  implementation, a **sequenced verify band** (functional review + live-verify →
  UI + security on the stabilized diff), one **bounded fix pass** per rejected
  return, and a **correctness floor** that refuses to commit a broken phase.
- **`PROPOSE → MAKE → CHECK → FIX` model policy** — Opus reasons/designs and
  independently checks, Sonnet makes product source, Haiku does plumbing; Opus
  never mutates product source. Model **aliases** ride the host's generation.

### File-native shared brain
- All coordination lives in committed `.devx/` Markdown — a project context file,
  an append-only log, per-workstream roadmaps/plans, and summarized handoffs.
- **Resume from files, never chat history** — runs survive crashes and resume
  losslessly across sessions, machines, and fresh clones.
- **Idempotent shipping** — an existing open PR is resumed and a closed/merged one
  returns to the operator, so an interrupted run never duplicates work.

### Knowledge & retrieval
- **FTS5 knowledge vault** — curated, project-agnostic SWE knowledge with
  frontmatter + a `related` / `[[wikilink]]` graph, searched via `devx kb_search`.
- **Per-project index** — durable `.devx/` research and learnings are FTS5-indexed
  so a lesson one phase learns **ranks** for the next.
- **Validation gate** — `devx validate --promote-to` is the sole automated vault
  writer (provenance, dead links, collisions, path-leakage, dangling-link checks).
- **Retrieval CLI** (`devx`, stdlib-only) — `kb_search`, `fetch`, multi-engine
  `search`, `github_search`, `index`, `validate`, `handoff_check`, `state check`,
  and `doctor`.

### Companion skills
- **`/devx:devx-explain`** — read-only cited Q&A over the repo + vault, and
  per-component documentation generation.
- **`/devx:devx-vault`** — curate the knowledge vault on demand (paste or research).
- **`/devx:devx-init`** — optional bootstrap (doctor, install helpers, index, scaffold).

### Safety rails
- Independent review in a clean context against pre-committed criteria; minimal
  base-tool allowlists; a `model_guard` PreToolUse hook (opus allowlisted to the
  judgment roles); a thin catastrophic-command denylist; a token/cost monitor; and
  operator gates on every irreversible VCS action.
- VCS modes: **local** (default — branch + commits), **remote** (push + PR via
  `gh`), or **none**.

### Optional integrations
- `codebase-memory-mcp` source graph for reuse/dedup discovery, `ast-grep` for
  structural search, and an **operator-gated, advisory Codex second opinion**
  (roadmap/code/security) whose output is never authoritative.

### Tooling & compatibility
- Tested with **Claude Code 2.1.218** and **Python 3.11 / 3.13**.
- A per-module `pytest` suite over the retrieval/index library
  (`uv run --with-requirements requirements-dev.txt pytest -q`).

Released under the [MIT License](LICENSE) by [Robensive](https://robensive.in).
