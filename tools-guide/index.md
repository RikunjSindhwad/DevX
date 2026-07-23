# Tools Guide — Index

How-to manuals for the tools agents actually invoke. Read `index.md` to find the tool, then read the
specific guide before using it. Where behavior is version-sensitive, record the tested version and
recheck live `--help` or primary documentation.

## Native (the DevX surface + git)

- `native/devx-cli.md` — `devx kb_search`, `fetch`, `search`, `github_search`, `index`, `validate`,
  `handoff_check`, `state`, `doctor`, and `vault`.
- `native/kb_search.md` — query craft for finding the right vault/project-memory material.
- `native/code-graph-mcp.md` — source-code discovery and structural navigation via
  `codebase-memory-mcp`, with ripgrep/ast-grep fallback when the MCP is unavailable.
- `native/ast-grep.md` — *optional* structure-aware search and safe multi-file AST-precise rewrites; probe
  for `ast-grep` and use it when present, degrade to ripgrep when absent. Notes the dirty-file overlay
  and the preferred `codebase-memory-mcp` graph tier.
- `native/codex-review.md` — optional, operator-gated external roadmap/code/security second opinion via
  inline `codex exec … -o …`; read-only, bounded, and never authoritative.
- `native/git.md` — clean commits, `.devx/` exclusion, and PRs with `git` / `gh`.
- `native/playwright.md` — UI verification/debugging. The `ui:browser` agent generates
  Playwright-Python scripts, uses the operator-provisioned `.devx/.venv`, reuses scripts, and cleans artifacts.
- `native/gui-desktop.md` — desktop/GUI app lifecycle: state machine, worker lifecycle, off-thread I/O, progress/cancel.

Execution (running code, tests, builds) uses native `Bash`/`Edit`/`Write` directly — there is no
wrapper. The guides below cover the **per-ecosystem** commands the implementer/reviewer call.

## Per-ecosystem (expandable — add the ones a project uses)
| Category | Dir | Examples |
|---|---|---|
| Package managers | `package-managers/` | uv, pip, pnpm, npm, cargo, go mod |
| Test runners | `test-runners/` | pytest, vitest/jest, go test, cargo test |
| Build / lint / format | `build-lint/` | ruff, eslint, prettier, mypy, tsc, make |

These directories are **extension points** — add a guide for each specific tool a project uses; none ship
by default. When a guide is absent, agents fall back to `project.md` context and the tool's `--help`.
Use `${CLAUDE_PLUGIN_ROOT}/templates/tools-guide-entry.template.md` for new guides so they include command
selection, focused runs, failure interpretation, and safety notes.
