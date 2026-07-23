# kb_search — query craft

`devx kb_search` finds curated knowledge fast. Good queries find actionable content in 1–2 tries; bad
ones return noise or nothing. The difference is specificity + context.

## Start specific, broaden on a miss
Include what you know — tech, variant, context — then drop one term at a time.
```
"fastapi dependency injection testing override"   → specific
"fastapi dependency injection"                    → drop "testing override"
"dependency injection python"                     → broadest useful
```

## Query patterns by task
| Task | Pattern |
|---|---|
| Implementing | `{api/pattern} {language/framework} {edge case}` |
| Choosing a package | `{ecosystem} package selection {problem}` |
| Reviewing | `{vuln class or pitfall} {tech}` (e.g. `idor authorization object level`) |
| Architecture | `{concern} pattern {constraint}` |

## Scope
- Default (`--scope vault`) for curated knowledge.
- `--scope project` to ask "did we already decide/hit this?" against `.devx/` (decisions, learnings,
  handoffs).
- `--scope all` when both matter.

## Special characters
Write normal queries. Hyphens, CVE IDs, slashes, version numbers, and operator-looking words are
sanitized (quoted as tokens) before FTS5 — no syntax errors. Don't add FTS5 operators (`OR`, `NEAR`,
column filters) yourself; use clearer terms.

## When to stop
- 3+ relevant hits → read the **top files** (not just snippets) and proceed.
- 0 hits after ~3 variations → `needs_web:true`; use `fetch`/`search`/native `WebSearch` for the gap.
- Don't run 10 queries when 3 suffice — each costs tokens and turns.

## Reading results
`score` is bm25 (negative; more negative = better). `section` is the breadcrumb (`path > H1 > H2`) so you
know where in the file the hit is. `tier` tells you whether it came from `fts5` (ranked) or `ripgrep`
(literal fallback).
