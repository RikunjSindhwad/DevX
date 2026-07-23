# ast-grep — structural code search & safe multi-file edits (optional, probe-and-fallback)

Structure-aware search and refactoring that beats line-based grep when you care about *shape*, not text:
find every caller, every duplicate pattern, every unsafe construct — and rewrite them AST-precisely so a
match never lands inside a string or comment. DevX does **not** wrap this in a `devx` subcommand: it's an
**optional** external CLI an agent shells out to **when present**, degrading to `ripgrep` when absent.
For semantic/source-graph discovery, prefer `codebase-memory-mcp` when available.

## When to reach for it (vs. ripgrep)
Use ast-grep when the thing you're matching is **structural** — a call shape, a node kind, a nesting — and
text matching would over- or under-match. Use ripgrep for plain literals/identifiers (it's faster for that).

- **Find callers / blast radius:** `foo($$$)` matches calls regardless of arg formatting (where `rg 'foo('`
  catches comments, strings, and `foobar(`).
- **Duplicate patterns:** the same idiom repeated across files — a reuse-before-creation signal
  (`agent-guide.md` §3).
- **Dead components / handlers:** a component or handler defined but never instantiated/wired.
- **Repeated literals / magic numbers:** the same literal scattered — a "give it a constant home" finding.
- **Unsafe constructs:** `eval($$$)`, `innerHTML = $X`, `subprocess.$M($CMD, shell=True)` — security review fodder.
- **UI slot wiring:** a slot/prop declared but never passed; a control rendered but never connected.
- **Handler-only tests:** tests that call a handler directly instead of dispatching a real event.
- **Broad refactor targets:** anywhere a single pattern spans many files and a textual sed would be unsafe.

## Probe and fall back (it's optional — never required)
Detect, then choose. Agents use the `ast-grep` binary only; do not call `sg` (it can be an unrelated system command and is not allowlisted):
```bash
AG=$(command -v ast-grep) && [ -n "$AG" ] && echo "AG=$AG" || echo "no ast-grep → ripgrep"
```
- **Present →** use it for the structural needs above; pass `--json` for agent-parseable output.
- **Absent →** degrade to `rg` (`tools-guide/native/code-graph-mcp.md` has the caller/blast-radius ripgrep
  technique). You lose AST precision, not the ability to do the job.
- Don't install it for the operator. If it's not on PATH, the ripgrep path is the answer.

> The short name `sg` is intentionally avoided: on some hosts it is an unrelated system command, and DevX
> agents are not allowlisted to call it.

## Search
```bash
ast-grep --pattern 'foo($$$)' --lang ts --json                # every call to foo (any args), JSON out
ast-grep --pattern 'console.log($$$)' -l js src/              # scoped to a path
ast-grep --pattern 'subprocess.$M($CMD, shell=True)' -l py    # unsafe-construct sweep
```
Metavariables: `$X` = one node · `$$$` = zero-or-more (arg lists, statements) · `$$X` = named multi-match.
`--json` emits one object per match (`file`, `range`, `text`, captured metavars) — parse a result set,
don't scrape lines. Pick `--lang/-l` to match the file's grammar (`ts`, `tsx`, `js`, `py`, `go`, `rust`,
`java`, …). For literal/identifier hunts, just use `rg` — it's faster and needs no grammar.

## Safe structural rewrite (`--rewrite`)
AST-precise search-and-replace across many files — the safe alternative to `sed` for a refactor, because it
**won't match inside strings or comments** and respects syntax:
```bash
ast-grep --pattern 'foo($A)' --rewrite 'bar($A)' -l ts            # preview the diff (no write)
ast-grep --pattern 'foo($A)' --rewrite 'bar($A)' -l ts -U         # -U/--update-all = apply in place
```
Captured metavars (`$A`, `$$$`) carry into the rewrite. **Always preview first** (omit `-U`), eyeball the
diff, then apply — and let the verify band re-run the originating gate on the result. A fix is not done
until the real gate passes.

## Dirty-file overlay — read the working tree first
When code is being edited *right now*, an index can serve stale results. **Order of truth:**
1. **`ripgrep` / `ast-grep` over the working tree first** — this catches untracked and in-flight edits that
   no index knows about yet.
2. **Then** any precomputed index or graph (`codebase-memory-mcp`, Zoekt) as an accelerator.

Never let an index answer for files that are mid-edit. ast-grep and ripgrep both read the live tree, so they
*are* the dirty-file overlay — run them ahead of any index, and treat index hits on changed files as
candidates to confirm against the working tree.

## codebase-memory-mcp is the preferred graph, not a replacement for live reads
`codebase-memory-mcp` is the preferred graph/index for large existing codebases — use it to find existing
symbols, call paths, duplicates, and architecture before adding code. On a **greenfield** project,
`ripgrep` + `ast-grep` over the small tree may be enough. On a dirty working tree, always confirm graph
hits against live files before making final claims.

## Large repos & docs-at-scale (opt-in tiers, never the baseline)
- **Zoekt (very large repos only):** Sourcegraph's `zoekt` is an optional *indexed* search
  tier for repos where repeated ripgrep/ast-grep scans become inefficient. It needs a Go binary plus a local
  index/daemon to be ergonomic — so it's **opt-in, never the default, never required**. `ripgrep`/`ast-grep`
  remain the baseline; consider Zoekt only when scan cost on a huge tree clearly justifies standing up an index.
- **codebase-memory-mcp graph:** preferred when installed; see `tools-guide/native/code-graph-mcp.md`.

## Verification
- Before claiming "X has no other callers," show the `ast-grep --pattern 'X($$$)'` (or `rg`) output that backs it.
- After a `--rewrite`, confirm the change compiles/tests pass and re-run the gate that surfaced the target —
  a structural rewrite that breaks a build isn't done.
- ast-grep matches the grammar, not semantics: it won't resolve dynamic dispatch, re-exports, or two
  same-named symbols across modules. Treat hits as a candidate set to confirm by reading.
