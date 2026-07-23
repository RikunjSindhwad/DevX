# devx CLI — the retrieval + index + log surface

The entire non-native tool surface. One command, `devx <subcommand>`. `log` is pure bash (works even if
Python/venv is broken); everything else is `scripts/devx_lib.py`. **No** execution layer lives here —
running code is native `Bash`. Output is JSON on stdout (a machine-readable result, not an input
contract). All durable artifacts are markdown.

## `devx log TYPE SOURCE "MESSAGE"`
Append a typed line to `.devx/log.md`. Append is atomic for lines < 4 KiB.
- TYPE: `START`/`COMPLETE` (agents) · `DISPATCH`/`GATE`/`DECISION`/`STAGE`/`NOTE` (orchestrator).
- Line written: `[2026-06-20T08:27:38Z] START reviewer — review T03 round 1`
- Example: `devx log START implementer "T03: token verify"`

## `devx kb_search "QUERY" [--scope vault|project|all] [--limit N]`
Search the curated vault and/or project knowledge (FTS5 BM25 keyword search) with a ripgrep fallback and
**graph neighbors** appended. The cascade short-circuits at 3 good hits.
- `--scope vault` (default): FTS5 over the vault; ripgrep(vault) fallback if FTS5 thin/absent.
- `--scope project`: FTS5 over the **project index** (durable `.devx` knowledge: research, learnings,
  decisions, architecture, project) + ripgrep(`.devx`) fallback — "have we decided/hit this before?"
- `--scope all`: both, FTS-first.
- **Graph neighbors.** After ranking, the top few vault hits' outgoing `[[wikilink]]`/`related:` targets
  are resolved (via `meta.doc_id` or filename stem) to vault docs and **appended** (capped) as
  `{path, section:null, snippet:<summary/first chunk>, tier:"graph", via:<the hit that linked here>}`,
  never reordering the primary ranking. The `tiers` list shows `graph:vault` when neighbors were added.
- Output: `{query, scope, tiers, count, needs_web, results:[{path, section, snippet, score?, tier, via?}]}`.
  `score` is bm25 (negative; more negative = more relevant) on keyword hits. `tier` is one of
  `fts5:*` (keyword), `graph` (a walked neighbor), or `ripgrep:*` (fallback);
  `via` names the linking hit. `needs_web:true` (primary keyword depth `< 3`, computed before graph
  neighbors) → consider the web.
- **Read the top files**, not just snippets. See `kb_search.md` for query craft.

## `devx fetch "URL" [--refresh] [--max-chars N]`
Fetch a URL, extract to text/markdown, and **cache** it under `.devx/cache/fetch/`. Use for library docs,
changelogs, RFCs, release notes — not the native `WebFetch` (no cache there).
- Modular subsystem in `scripts/lib/fetch/`: a **tiered cascade** (`github-raw → urllib → requests
  (if installed) → Wayback`) + an **extraction cascade** (`trafilatura → BeautifulSoup → stdlib strip`),
  over a content-hash cache. Output: `{ok, url, cached, path, chars, text, tier, extract?, ttl?, attempts?}`;
  total failure → `{ok:false, error, attempts}` (the `attempts` trail lets an agent cite *why* a fetch is weak).
- **Cache TTL (freshness).** A cached entry is served only while it is
  **fresh for its content class** (age = now − file mtime). `_ttl_for(url)` classifies by URL:
  changelog/releases/news/blog/feed → **~1 day**; rfc/spec/standard (`/rfc`, `datatracker.ietf`, `w3.org/TR`,
  `/spec`, `/standard`, `whatwg`) → **~90 days**; everything else → **~14 days** (the default). Past its TTL
  the entry is treated as a **miss** and re-fetched, overwriting the file (which resets its mtime). The
  rules live in a tunable module-level dict (`_TTL_RULES` + `DEFAULT_TTL`) in `scripts/lib/fetch/tiers.py`.
  `--refresh` still forces a miss regardless of freshness. A served hit reports the applied `ttl` (seconds).
- **Stdlib floor**: optional deps (`requests`, `trafilatura`, `beautifulsoup4`) are import-guarded —
  absent them, fetch still works via `urllib` + the regex strip. (The pentest-domain anti-bot browser
  tier is intentionally not ported.)

## `devx search "QUERY" [--limit N] [--engines a,b]`
The **default** web search → candidate URLs to `fetch`. **Multi-engine** with **reciprocal-rank-fusion**
dedupe (`scripts/lib/fetch/web_search.py`): default queries **DuckDuckGo + Bing + Yahoo** and RRF-fuses
whatever returns results. `--engines duckduckgo,bing,yahoo` (or `ddg,bing,yahoo`) overrides the set.
Output: `{ok, query, count, results:[{url, title, snippet}], engines, errors}`. Native `WebSearch` stays
the always-there alternative if all engines fail.

## `devx github_search "QUERY" [--kind code|repos] [--limit N]`
GitHub **code** (or repo) search via `gh` — native tools cannot do code search. Use to see how a library
is actually called. Output: `{ok, kind, count, results}` (repo, path, url, textMatches for code).
Needs `gh auth login` or the `github_token` userConfig.

## `devx index [--scope vault|project|all]`
Build/refresh an FTS5 index **plus the internal-link graph and per-doc metadata**. Incremental by file
hash (unchanged files skipped), rebuilds the FTS5 index, prunes deleted files. For each indexed doc it also:
- records `related:` slugs + inline `[[wikilinks]]` into a **`links`** table (replaced on change, pruned on
  delete) — the cross-reference graph `kb_search` walks and `validate` resolves against;
- parses frontmatter into a **`meta`** table — `title` (frontmatter `title:` else first `# H1`), `doc_id`
  (frontmatter `id:` else the filename stem), `tags`, `summary`. This is what `validate`'s dedup reads
  instead of re-scanning every vault file (and what graph snippets come from).
- `--scope vault` (default): the curated vault (`<vault>/**/*.md` → `vault/mdvault-devx.sqlite`). Run
  after editing or curating vault content.
- `--scope project`: the **durable** `.devx` knowledge (research/learnings/decisions/architecture/
  project → `.devx/index/mdvault-project.sqlite`). Volatile files (log/state/handoffs/reviews) are NOT
  indexed. Run after research/learnings are appended.
- `--scope all`: both.
- Output: `{ok, vault?:{db,files,chunks,links,meta,changed}, project?:{…}}` (`meta` = rows in the meta
  table). Without FTS5 it returns `{"ok":false,"error":"no such module fts5"}` and kb_search degrades to
  ripgrep.
- Both DBs are **derived** — git-ignored, rebuildable (new tables rebuild cleanly on the next index run).

## `devx validate FILE [--promote-to CAT/NAME.md] [--update] [--offline] [--max-age-days N]`
The **promotion validation gate**. Validates mechanical properties of a candidate before it can enter
the shared vault. It does not establish factual truth or source authority. Checks: **stale references**
(definitive 404/410 source links → fail; transient/auth/network failures → warning),
**provenance** (`> Source: … · {date}` required; older than `--max-age-days`, default 365 → warn),
**dedup** (same title — frontmatter `title:`, else the H1 — or target filename already in the vault → fail;
`--update` overwrites that one), **generalization** (an absolute project path is an un-stripped leak →
fail), and **internal links** (`related:`/`[[wikilink]]` targets that resolve to no known vault `id`/stem →
a `dangling-links` **warning**, never a failure — the target may simply be promoted next). A target may be a
bare id (`[[idempotency-keys]]`) **or** a `category/id` path (`[[patterns/idempotency-keys]]`) — both resolve
(the path form matches on its last segment).
- **Thematic-overlap (fuzzy) WARNING.** When there is no *exact* dup and the FTS index is available, the
  candidate's `title + summary` is OR-searched against the vault; a strongly-overlapping existing entry
  (clears the documented bm25 floor **and** shares ≥ half the candidate's content terms) raises a
  `thematic-overlap` **warning** naming the path and a `near_duplicates:[…]` list. It's advisory, **never a
  failure** — confirm it's complementary (cross-link it in `related:`) or `--update` if it's truly the same
  entry. **Entries the candidate already cross-links are suppressed** (deliberate siblings ≠ duplicates). The dedup metadata is read from
  the index `meta` table (no per-file scan); with no index it falls back to scanning the vault.
- With `--promote-to`, the gate is **enforced by code**: on PASS it writes the file into the vault and
  reindexes; on FAIL it writes nothing. Agents never hand-write into `vault/`. A curator still reviews
  correctness, generality, and source quality before promotion.
- **Path-safe by code:** the `--promote-to CAT/NAME.md` target is constrained to land **inside the
  vault** — `../` traversal, absolute paths, and symlink escapes are rejected, so a promotion can never
  write outside `vault/`.
- `--offline` skips network link checks (URLs → "unverified" warnings, never failures).
- Output: `{verdict:"pass"|"fail", checks:[…], stale_refs:[…], duplicate, near_duplicates:[…],
  dangling_links:[…], warnings:[…], promoted?}`. **Exit code is the verdict** (non-zero = rejected) so
  callers/CI can branch on it.

## `devx handoff_check [PATH] [--workstream SLUG] [--agent NAME] [--newer-than ISO]`
The **continuity gate**. The orchestrator runs this after every agent returns to confirm the agent wrote
a valid handoff (existence breaks resume otherwise). Checks the file exists, is non-empty, and has all
six sections (Summary/Changes/Decisions/Verification/Issues/Next) **plus a valid `Status:` line** — the
value must be one of `complete` | `partial` | `blocked`. A missing or unrecognized `Status:` makes
`ok` false (and exits non-zero), even when all six sections are present.
- Give an explicit `PATH`, or `--workstream SLUG [--agent NAME]` to validate the **newest** matching
  handoff (`*-{agent}-*.md`) under that workstream. `--newer-than` ignores handoffs older than an ISO ts.
  The orchestrator pre-allocates a unique `return_as` and should therefore use explicit `PATH`; the
  newest-match form remains a compatibility/discovery fallback. Parallel fan-in validates every exact
  expected path.
- Output: `{ok, exists, sections_present, sections_missing, status, matched?}`. **Exits non-zero** when
  the handoff is missing or malformed (including an absent/invalid `Status:`) → the orchestrator re-dispatches.

## `devx state check [--workstream SLUG]` *(gate)*
**State consistency gate.** Reads `state.md` and the current phase file and flags mismatches: reports
`STATUS:COMPLETE` while phases remain PAUSED/NOT-STARTED, and an advisory workstream-scoped audit that
matches each structured DISPATCH entry to its exact `return_as` handoff. Other workstreams and unrelated
handoff files cannot hide a missing return. Legacy unscoped DISPATCH lines are reported as ignored.
Exits non-zero on state inconsistency — the dispatch audit itself remains advisory because a cancelled
dispatch can be legitimate.
- Output: `{ok, workstream, status, issues:[…], advisory:[…]}`. **Exits non-zero** on detected
  inconsistency.

## `devx vault stats [--split-threshold N]` *(optional curation aid)*
Vault **layout** health for the emergent-sub-folder model (flat categories at top; sub-divide a category
into one-level sub-folders only once it grows). Not a core-loop step — use when you want to check whether
a vault category has grown large enough to split. Walks the vault tree and reports the per-category
distribution — total + directly-held `.md` counts and the sub-folder breakdown — and flags any folder
holding **more than N files directly** (default 20) as a "time to split" signal.
- Output: `{ok, vault, total_files, split_threshold, categories:[{category, files, direct, oversized,
  subfolders:[{name, files, direct}]}], split_suggestions:[…], indexed?:{files, chunks, links}}`.
- Disk is the source of truth for layout (works with no index); `indexed` counts are best-effort enrichment
  when the FTS index exists. Retrieval never depends on the tree shape — this is a **curation aid**, so a
  split is a human decision made with data, not an automatic reorg.

## `devx doctor`
**Environment preflight gate** for `/devx:devx-init`. Probes the host for every tool the plugin depends on and
emits a structured report so setup failures are caught before any workstream runs.

Output: `{ok, python, fts5, package_manager, checks:[{tool, present, required, status, why, install?}], missing_required:[], install_hints:[]}`.

**Required tools** (missing any → `ok:false`, **exits non-zero**): `python≥3.11`, `git`, `rg`.
**Strongly recommended** (absent → `status:"degraded"`, NOT a failure): `sqlite3-fts5` — without it `kb_search` degrades to ripgrep (slower, unranked).

**Optional tools** (absent → degrade gracefully, not a failure): `codebase-memory-mcp`, `ast-grep`,
`ugrep`, `gh`.

`codebase-memory-mcp` is the preferred source graph for reuse/dedup discovery. If absent, agents use
live `rg`/`ast-grep` and must state the fallback in handoffs. Install it with
`${CLAUDE_PLUGIN_ROOT}/bin/install-codebase-memory-mcp` or from a verified release at
https://github.com/DeusData/codebase-memory-mcp/releases/latest.

For each missing tool, `checks[].install` carries the correct install command for the detected OS package
manager. `install_hints` repeats all missing-tool install commands at the top level for easy copy-paste.

**Exits non-zero if any required tool is missing** — callers and CI branch on `$?` exactly as
they do for `validate` and `handoff_check`. (FTS5 is recommended, not required: absent → degraded, kb_search uses ripgrep.)

### Indexer model (for maintainers)
Markdown is chunked at headings; each chunk stores a `path > H1 > H2` **breadcrumb** so a hit carries
its location. External-content FTS5 (`content='chunks'`) keeps canonical text in a normal table and the
FTS index beside it. Alongside the chunks: a `links(file_id, target)` table holds each doc's frontmatter
`related:` slugs + inline `[[wikilinks]]` (the cross-reference graph `kb_search` walks and the gate
resolves against); a `meta(file_id, title, doc_id, tags, summary)` table holds per-doc metadata so dedup
and link resolution read the index instead of re-scanning every file. No daemon, no watcher — rebuild on
demand. New tables rebuild cleanly. (Stdlib-only: frontmatter is parsed with regex, not a YAML
dependency.) The complete retrieval stack is FTS5 (BM25) + ripgrep + links graph — no semantic/vector
tier.
