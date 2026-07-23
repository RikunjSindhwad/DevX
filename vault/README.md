# DevX Knowledge Vault

Curated, **project-agnostic** software-engineering knowledge, FTS5-indexed for `devx kb_search`.
This is the *global* layer (shared across all projects). Per-project memory lives in each repo's
`.devx/` and is searched with `--scope project`.

## Categories
| Dir | Holds |
|---|---|
| `languages/` | Idioms, gotchas, stdlib patterns per language |
| `frameworks/` | Framework best-practices (web, data, CLI…) |
| `patterns/` | Architecture & design patterns |
| `testing/` | Test strategies, TDD, fixtures, fakes |
| `security/` | OWASP, secure-by-default checklists |
| `performance/` | Perf patterns and common pitfalls |
| `packages/` | Package-selection guidance per ecosystem |
| `ops/` | Build, CI, release, observability |

## Layout (emergent sub-folders)
These eight categories are the **stable top level** — don't add or rename them lightly. Within a category,
let structure **emerge as it grows**: keep entries flat until a category gets large, then split the natural
clusters into **one level of sub-folders** (e.g. `languages/python/asyncio.md`, `patterns/resilience/circuit-breaker.md`).
The indexer globs `**/*.md` recursively and `--promote-to {category}/{subtopic}/{slug}.md` is fully
supported, so nesting costs nothing mechanically.

The folder tree is **coarse navigation for humans/git** — it is *not* how knowledge is found. Findability is
**metadata + links + search**: `type`/`tags`, the `related:`/`[[wikilink]]` graph, and `devx kb_search`. So a
flat folder never hurts retrieval; it only hurts browsing. Don't pre-build a deep taxonomy (early guesses age
badly) — run **`devx vault stats`** to see the per-category distribution; it flags a folder holding too many
files directly as a "time to split" signal, so re-organizing is a human decision made with data.

## Format
One topic per `.md` file. Use `#`/`##`/`###` headings — the indexer chunks on them and stores a
`path > H1 > H2` breadcrumb so every hit carries its location. Keep entries practical and dense.

Entries carry **YAML frontmatter** (`id`, `title`, `type`, `tags`, `summary`, `related`, `created`) — see
`../templates/vault-entry.template.md` for the shape. The frontmatter is not decoration:
- `title` (falling back to the H1) is the **dedup key** the gate uses.
- `id` is the stable **slug** other entries link to — keep it equal to the filename stem.
- `related:` typed cross-refs and inline `[[wikilinks]]` form a **link graph**: `devx index` records them in
  a `links` table, and `devx validate` resolves them (a `related:`/`[[…]]` target that isn't a known vault id
  is a **dangling-link warning**, never a hard failure — the target may just be promoted next).

Plain-markdown entries (no frontmatter) still index and rank fine — frontmatter is what powers dedup-by-title,
the link graph, and richer snippets.

## Index
Rebuild after editing: `devx index` (incremental by file hash; rebuilds the FTS5 index).
The DB (`mdvault-devx.sqlite`) is **git-ignored** — it is derived, rebuildable from the `.md` files.

## Growth (see ARCHITECTURE.md §KB lifecycle)
Seeded small on purpose. Automated/agent-assisted promotion goes through the validation gate
(`devx validate .devx/cache/promote/{candidate}.md --promote-to {cat}/{name}.md`), the sole automated
promotion writer. The gate checks
provenance/date, definitive 404/410 links, collisions (by `title`/filename), absolute project-path
leakage, and internal-link resolution; the vault entry is written and the index rebuilt **only on
PASS**. These checks do not prove truth, authority, or full generality, so editorial review remains
required.

1. **`/devx:devx-vault`** — the on-demand curator skill. PASTE mode generalizes content you hand it; RESEARCH
   mode researches a topic and synthesizes an entry. Both stage a frontmatter'd candidate and promote it
   through the gate.

2. **Agent-assisted promotion** — the researcher may stage authoritative, generalized candidates under
   `.devx/cache/promote/` and request promotion; the orchestrator/operator decide whether the shared vault
   should change. The docs agent curates learnings at ship after the ship gate. Same validation gate.

3. **Maintainer curation** — maintainers may deliberately edit vault `.md` files directly and run
   `devx index` to rebuild. This bypasses the promotion gate, so the maintainer owns source review,
   generalization, collision checks, and link validation.
