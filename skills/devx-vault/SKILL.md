---
name: devx-vault
model: sonnet
description: >
  Add knowledge to the curated dev-knowledge vault, on demand. Two modes: (1) PASTE —
  the operator hands you content (notes, an article excerpt, a snippet, a hard-won
  lesson) and you generalize it into a vault entry; (2) RESEARCH — the operator names a
  topic and you research it (web search + fetch, cross-checked against what's already in
  the vault) and synthesize an entry. Either way you write a frontmatter'd, generalized
  candidate and promote it THROUGH the validation gate
  (devx validate <candidate.md> --promote-to <target.md>),
  which is the sole automated promotion writer — it rejects collisions, definitive dead
  sources, missing provenance, and absolute project-path leaks, and resolves [[wikilinks]]. Never hand-writes
  into vault/.
disable-model-invocation: true
allowed-tools:
  - Read(./**)
  - Glob
  - Grep
  - Bash(devx kb_search*)
  - Bash(devx search*)
  - Bash(devx fetch*)
  - Bash(devx validate*)
  - Bash(devx index*)
  - Bash(devx vault*)
  - Bash(devx log*)
  - WebSearch
  - WebFetch
  - AskUserQuestion
---

# /devx:devx-vault — curate the knowledge vault

`allowed-tools` is a one-turn preapproval list, not a sandbox. Candidate
creation remains limited by this skill contract to `.devx/cache/promote/`, and
shared-vault writes still go through the existing validation/promotion command.

> **On-demand operator tool.** Vault curation at ship is **default-on** (gated) — stage 06 offers to promote a workstream's generalizable findings, defaulting to yes, and the operator can decline. `/devx:devx-vault` is the **on-demand** path: curate knowledge into the vault outside a ship (e.g. file a hard-won lesson or research a topic for future projects), through the same promotion validation gate.

You add durable, **project-agnostic** software-engineering knowledge to the shared `vault/`. The vault
compounds across every project, so the bar is high: each entry is **generalized** (no project specifics),
**sourced**, **non-duplicating**, and **cross-linked**. You never write into `vault/` directly — you stage
a candidate and let the **gate** (`devx validate <candidate.md> --promote-to <target.md>`) write it, exactly like the pipeline's
researcher and docs agents do.

On startup: `devx log NOTE orchestrator "vault curation in $(pwd)"`.

Vault entries are shared across repos. Before promoting anything, classify whether the material is
general engineering knowledge or a project-local finding. Project-local bugs, review findings,
duplicate-code findings, and UI polish debt belong in the target repo's `.devx/backlog.md` or workstream
artifacts, not in the shared vault. If the operator named a different repo than `pwd`/git root, ask before
writing project-local backlog entries.

---

## Two modes

Pick from the operator's request (ask with `AskUserQuestion` only if genuinely ambiguous):

- **PASTE** — they gave you content to file (notes, an excerpt, a snippet, a lesson). Generalize it.
- **RESEARCH** — they named a topic. Research it, then synthesize an entry from authoritative sources.

---

## Step 1 — Check the vault first (no duplicates)

Before writing anything, find out what the vault already knows:

```bash
devx kb_search "<the topic, in a few phrasings>" --scope vault
```

Read the top hits, not just snippets. Then decide:

- **Already well-covered** → tell the operator; offer to **update** the existing entry (`--update`) instead
  of adding a near-duplicate. Don't create a second entry on the same topic.
- **Partially covered** → the new entry should **complement** it. Note the existing entry's `id` — you'll
  add it to `related:` so the two cross-link.
- **Not covered** → proceed to author a new entry.

This is the first line of dedup; the gate's dedup check is the backstop, not a substitute for looking.

---

## Step 2 — Gather the material

### PASTE mode
Work from what the operator gave you. If it cites a source (URL/book/RFC), keep it for provenance. If it
has none, ask the operator for one — promoted knowledge should be attributable. Generalize aggressively:
strip internal names, hosts, secrets, and **absolute project paths** (the gate rejects those as un-stripped
leaks). What survives must be true beyond this one project.

### RESEARCH mode
1. `devx search "<topic>"` → candidate URLs (multi-engine, RRF-fused). Fall back to native `WebSearch`.
2. `devx fetch "<url>"` the authoritative ones (docs, RFCs, changelogs, reputable write-ups) — it caches and
   text-extracts. Prefer primary sources over blog summaries.
3. Synthesize a **dense, practical** entry in your own words. Cite the real source URL(s) you used — never
   fabricate a citation, and never cite a page you didn't actually fetch.

---

## Step 3 — Author the candidate (frontmatter + body)

Write to `.devx/cache/promote/{slug}.md` using
`${CLAUDE_PLUGIN_ROOT}/templates/vault-entry.template.md` as the shape. Candidate requirements (only
some are mechanically enforceable by the gate):

- **Frontmatter**: `id` (== the filename stem == the slug others link to), `title` (== the H1), `type`
  (mirrors the target category), `tags`, `summary`, `created` (today, ISO).
- **`related:` + `[[wikilinks]]`** — cross-link to entries that actually exist. Use the `id`s you saw in
  Step 1's `kb_search` hits. A link to an entry that isn't in the vault yet is a **warning, not a failure**
  (you may be about to promote it) — but don't invent slugs; prefer ones you've confirmed.
- **Provenance line** (required): `> Source: {url} · promoted by /devx:devx-vault · {YYYY-MM-DD}`.
- **Generalized**: no absolute paths, internal names, or secrets.

Choose the target category from the vault's structure (see `${CLAUDE_PLUGIN_ROOT}/vault/README.md`):
`languages/ frameworks/ patterns/ testing/ security/ performance/ packages/ ops/`. If the category already
has **sub-folders** (e.g. `languages/python/`), promote into the matching one (`languages/python/{slug}.md`);
nesting is fully supported. Don't invent a deep new hierarchy — keep it flat until a category is clearly
large (`devx vault stats` shows the distribution and flags an oversized flat folder).

---

## Step 4 — Promote THROUGH the gate (the only writer)

```bash
devx validate .devx/cache/promote/{slug}.md --promote-to {category}/{slug}.md
```

The gate checks **stale references** (definitive 404/410 source links → fail; transient/auth/network
failures → warning), **provenance** (required, ISO date),
**dedup** (same `title:`/filename already in the vault → fail; add `--update` to deliberately overwrite that
one), **generalization** (an absolute project path → fail), and **internal links** (`related:`/`[[…]]`
targets that don't resolve → a `dangling-links` **warning**). On **PASS** it writes the file into the vault
and rebuilds the index. On **FAIL** it writes nothing.

Passing the gate does not prove factual truth, authority, or complete generalization. Review the
candidate and its primary sources before promotion.

- If it **fails**: read `checks[]`, fix what it reports (broken link, missing source, a real duplicate, a
  leaked path), and re-run. Never work around the gate by hand-writing into `vault/`.
- If it **passes with `dangling-links`**: either add the missing target entry too, or fix the slug to point
  at an entry that exists. A deliberately forward-referencing link is acceptable — surface it, don't hide it.
- Offline? add `--offline` to skip network link checks (URLs become "unverified" warnings, never failures).

---

## Step 5 — Report

Tell the operator concisely:
- What was promoted (path in the vault) **or** why it was rejected/updated instead.
- Any `dangling-links` warning and what you did about it.
- If you promoted several related entries, that they now cross-link.

---

## Rules
- **The gate is the sole writer.** You only ever write `.devx/cache/promote/**`; `devx validate
  --promote-to` writes `vault/`. Never hand-file into a vault category, never run a bare `devx index` to
  force an entry in.
- **No duplicates.** Search first (Step 1); the gate's dedup is the backstop. Prefer `--update` over a
  near-twin.
- **Generalize hard.** The vault is shared across all projects. If it only makes sense in this repo, it
  belongs in `.devx/`, not the vault.
- **Cite truthfully.** Every entry carries a real `> Source:`; never fabricate one, never cite an unread page.
- **Follow the links.** Fill `related:`/`[[…]]` with real entry `id`s so the knowledge graph stays connected.
