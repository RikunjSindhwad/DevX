# code graph — codebase-memory-mcp structural discovery

DevX retrieval is **text-first** for knowledge (`kb_search` over the vault/project). Source-code reuse
and impact analysis should use the repo's structural graph when available. DevX ships a plugin-level MCP
declaration for `codebase-memory-mcp`; the operator still needs the `codebase-memory-mcp` binary installed
locally. The launcher checks `CODEBASE_MEMORY_MCP_BIN`, plugin-local compatibility paths,
`~/.local/bin/`, then PATH. `/devx:devx-init` offers the bundled checksum-verifying installer.

DevX does **not** wrap this in a `devx` subcommand. The MCP runs as its own process; live `rg` and
`ast-grep` remain the fallback and the dirty-working-tree source of truth.

## When to use
- Before adding a new function/class/component/module: find existing code to reuse or extend.
- Before changing a shared function/type: trace callers and affected paths.
- During review/security: map blast radius and duplicate/similar implementations.
- During planning: identify existing APIs, routes, repositories, services, tests, and fixtures.

## Required project hygiene

Create a project `.cbmignore` when the repo has non-product folders that would pollute results:

```gitignore
.devx/
.codebase-memory/
node_modules/
dist/
build/
coverage/
.turbo/
.next/
```

Add generated migration snapshots or vendor trees when they dominate results, for example
`apps/api/drizzle/meta/` or `vendor/`. Do not ignore real source directories just to quiet a noisy query.

## MCP tools

Use the MCP tools directly when they are available:

| Need | Tool |
|---|---|
| Index or refresh the repo graph (bootstrap/init only) | `mcp__plugin_devx_codebase-memory-mcp__index_repository` |
| Check indexed projects | `mcp__plugin_devx_codebase-memory-mcp__list_projects` |
| Check freshness/counts | `mcp__plugin_devx_codebase-memory-mcp__index_status` |
| Find existing symbols by name/keyword | `mcp__plugin_devx_codebase-memory-mcp__search_graph` |
| Search indexed source text | `mcp__plugin_devx_codebase-memory-mcp__search_code` |
| Read exact source for a symbol | `mcp__plugin_devx_codebase-memory-mcp__get_code_snippet` |
| Trace callers/callees | `mcp__plugin_devx_codebase-memory-mcp__trace_path` |
| Architecture overview | `mcp__plugin_devx_codebase-memory-mcp__get_architecture` |
| Custom duplicate/graph queries | `mcp__plugin_devx_codebase-memory-mcp__query_graph` |
| Changed-file impact map | `mcp__plugin_devx_codebase-memory-mcp__detect_changes` |
| Inspect available node/edge types | `mcp__plugin_devx_codebase-memory-mcp__get_graph_schema` |

Normal role agents receive only the read tools above. `index_repository` is reserved for bootstrap/init;
mutation tools such as `delete_project`, `manage_adr`, and `ingest_traces` are not granted. Do not replace
the enumerated grants with an MCP wildcard.

If the MCP client exposes only CLI access, the equivalent pattern is:

```bash
codebase-memory-mcp cli index_repository '{"repo_path":"."}'
codebase-memory-mcp cli list_projects
codebase-memory-mcp cli search_graph '{"project":"<project>","query":"CaseService","limit":20}'
codebase-memory-mcp cli search_code '{"project":"<project>","pattern":"defineAbilityFor","limit":20}'
codebase-memory-mcp cli get_code_snippet '{"project":"<project>","qualified_name":"<qualified-name>"}'
codebase-memory-mcp cli trace_path '{"project":"<project>","function_name":"createCase","direction":"both"}'
```

Note: CLI arguments are JSON. Most tools require the indexed `project` name returned by `list_projects`
or `index_repository`; snippet lookup requires `qualified_name`, not just `function_name`.

## Discovery workflow

1. Ensure the repo is indexed. During bootstrap/init, run `index_repository` if it is missing or stale;
   otherwise report the stale index and use live search until the orchestrator refreshes it.
2. Search by symbol/feature name with `search_graph`.
3. Use `get_code_snippet` for the best candidates before writing new code.
4. Use `trace_path` or `query_graph` when changing a shared path.
5. Confirm changed/untracked files with live `rg`/`ast-grep` before final claims.

Record this in handoffs as `Code discovery: codebase-memory-mcp search_graph/search_code + rg` or the
exact fallback used. A handoff that adds new code without naming discovery is incomplete.

## Ripgrep fallback (always available)
Textual, but good enough when the MCP is unavailable:
```
rg -nw 'refreshToken'              # every mention (definition + call sites)
rg -nw 'refreshToken\('            # call sites only (word-boundary + open paren)
rg -n 'def refreshToken|function refreshToken|func refreshToken|fn refreshToken'   # the definition
```
Blast radius = iterate: callers of `refreshToken`, then callers of *those*, until you hit entry points.

**Limits (state them, don't pretend precision):** ripgrep can't resolve overloads, dynamic dispatch,
re-exports, or two same-named symbols in different modules. Treat the result as a candidate caller set to
verify by reading, not a proven graph.

## Verification
- Before claiming "X has no existing equivalent," show the `search_graph`/`search_code` query or the
  fallback `rg`/`ast-grep` output.
- Before claiming "X has no other callers," show `trace_path` or the fallback `rg -nw 'X\('` evidence.
- A localized change with zero external callers may proceed; a wide blast radius must be reflected in
  the plan, tests, and review notes.
