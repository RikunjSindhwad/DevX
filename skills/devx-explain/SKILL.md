---
name: devx-explain
description: >
  Understand an existing codebase without changing it. Two modes: (1) ASK — read-only
  Q&A over the repo + the dev-knowledge vault ("what does X do?", "where is Y handled?",
  "how does auth flow?"); (2) DOCUMENT — analyze the codebase and generate per-component
  docs (docs/components/*.md) by fanning out one docs agent per component. Read-only to
  source; only writes under docs/ and .devx/.
model: sonnet
effort: high
disable-model-invocation: true
allowed-tools:
  - Read(./**)
  - Edit(./docs/**)
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
  - Bash(devx kb_search*)
  - Bash(devx index*)
  - Bash(devx log*)
  - Bash(git ls-files*)
  - Bash(git log*)
  - Bash(rg *)
  - Bash(ugrep *)
  - Bash(cat *)
  - Bash(ls *)
  - Bash(find *)
  - Bash(mkdir *)
  - Bash(pwd)
  - Agent
  - AskUserQuestion
---

# /devx:devx-explain — understand the codebase

`allowed-tools` is a one-turn preapproval list, not a restriction boundary.
ASK mode remains source-read-only by this skill contract; host permissions and
hooks still govern every call. Durable explain state lives under `.devx/`.

Read-only comprehension. You never modify source. You orient via the repo map and answer precisely, or
you produce durable component documentation. Cite `file:line` for every claim (verify-before-claim).

On startup: `devx log STAGE orchestrator "explain session in $(pwd)"`. Search project memory and the
vault freely: `devx kb_search "<q>" --scope all`.

Before answering or dispatching docs/scout agents, establish the same target contract used by `/devx:devx`:
`TARGET_REPO`, `CURRENT_CWD`, and `GIT_ROOT`. If the operator's question names another repo than the live
cwd/git root, stop and ask which repo to inspect. When using `codebase-memory-mcp`, verify the project
matches that target and has useful indexed content before treating it as evidence; otherwise say the graph
is unavailable and use live `Grep`/`Glob`/`rg`.

## Explain Session State

`/devx:devx-explain` is not the delivery pipeline, but any sub-agent you dispatch still needs a durable place
to log handoffs. Before dispatching `scout` or `docs`, create an explain workstream:

```
.devx/workstreams/explain-{YYYYMMDD-HHMM}/
  brief.md
  state.md
  handoffs/
  reviews/
  research/
```

Use the slug `explain-{YYYYMMDD-HHMM}` unless the operator supplied a better topic slug. Write:

- `brief.md`: the question or documentation scope, plus "mode: explain".
- `state.md`: a single NEXT ACTION (`answer question`, `map components`, or `complete`).

Pass `workstream={slug}` and `return_as={unique handoff filename}` in every `Agent` dispatch brief. This keeps
explain-mode agent calls compatible with the shared handoff contract without pretending this is a normal
delivery workstream. Confirm each exact handoff path is absent before dispatch and validate that exact path
with `devx handoff_check` after return.

If `.devx/project.md` is missing or stale, create the explain workstream first, then dispatch
`devx:recon:scout` (haiku) with that workstream to refresh the repo map before answering.

## Mode A — ASK (default)
The operator asks a question about the codebase.
1. Locate the relevant code with `Grep`/`Glob` (and `ugrep` for long-line files). Read enough to be
   correct, not everything. Use `codebase-memory-mcp` first only when its project has passed the target
   and health check above.
2. Consult the vault for the concept if useful (`devx kb_search`).
3. Answer concisely with **`file:line` citations** and, where helpful, a small flow ("request →
   `router.py:42` → `auth.verify():auth.py:88` → …"). State unknowns plainly; never guess.
4. Offer to go deeper or to generate component docs (Mode B) for the area discussed.

## Mode B — DOCUMENT (on request)
Generate per-component documentation for the codebase (or a subtree).
1. **Enumerate components** from the repo map: modules/packages/services with a coherent responsibility
   (e.g. each top-level package, each service, each significant module). Present the list + the target
   (`docs/components/`) and confirm scope via `AskUserQuestion` for a large repo.
2. Ensure an explain workstream exists, then **fan out** — dispatch `devx:docs:docs` in *map* mode, **one
   per component, in parallel** (multiple `Agent` calls in one message). Each dispatch gets
   `workstream={explain slug}`, `mode=map`, `component`, the component's file paths, and a unique
   `return_as={NN}-docs-map-{component}.md`. Each writes
   `docs/components/<name>.md`: purpose, public API/exports,
   key types, dependencies (in/out), invariants/gotchas, and entry points — every claim cited.
   After the fan-out returns, validate every
   `.devx/workstreams/{slug}/handoffs/{return_as}` path; assemble only when all component handoffs pass.
3. **Assemble** `docs/components/README.md` as an index (component → one-line purpose → link), and note
   any cross-cutting findings.
4. Optionally refresh `.devx/architecture.md` if the component pass revealed the structure drifted from
   the doc. Re-run `devx index --scope project` if you wrote anything under `.devx/`.

## Gates
- ASK mode: none — it's read-only.
- DOCUMENT mode for a large repo: confirm the component list + scope before fanning out (cost control).

## Rules
- **Read-only to source.** Never edit code from this skill; only `docs/` and `.devx/`.
- **Cite or say "unknown."** Every claim is `file:line`-backed; no inference presented as fact.
- **Fan out, don't serialize.** Component docs are independent — dispatch them concurrently, one agent
  per component, each in a clean context, but only after each has a unique component name and shared
  explain workstream for handoffs. Fan-in is all-or-nothing over the pre-allocated exact handoff paths.
- **Reuse, don't duplicate.** If `docs/` already documents a component, update it rather than re-create.
