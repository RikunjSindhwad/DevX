<!--
VAULT ENTRY TEMPLATE — the shape of a curated vault doc. Used by /devx:devx-vault and the docs agent
(curate mode). The entry is NEVER hand-written into vault/: stage it (e.g. under .devx/cache/promote/)
and promote it through the gate —
`devx validate .devx/cache/promote/{candidate}.md --promote-to {category}[/{subtopic}]/{slug}.md` (a
category may sub-divide into one-level sub-folders as it grows — see vault/README.md "Layout") — which
writes the vault and reindexes ONLY on PASS. The gate enforces what this template sets up:
  • provenance     — the `> Source: … · {date}` line is REQUIRED (and must carry an ISO date).
  • generalized    — no absolute project paths / internal names / secrets (the vault is shared).
  • dedup          — keyed on `title:` (below) and the filename; collide → rejected (use --update to overwrite).
  • internal links — `related:` slugs + inline [[wikilinks]] that don't resolve to a vault id are a
                     WARNING, not a failure (the target may simply be promoted next). A [[wikilink]] may use
                     the bare id ([[idempotency-keys]]) or a category path ([[patterns/idempotency-keys]]) —
                     both resolve; prefer the bare id for a consistent link graph.
`devx index` parses the frontmatter + links into the FTS5 index and the `links` graph. Keep `id` == the
filename stem == the slug others link to.
-->
---
id: {kebab-slug}                 # stable identifier — what others [[link]] to; keep == filename stem
title: {Human Readable Title}    # MUST equal the H1 below; this is the dedup + snippet key
type: {pattern|language|framework|testing|security|performance|package|ops}   # mirrors the vault category
tags: [{tag}, {tag}]             # lowercase, topical — aids FTS recall and scanning
summary: {one sentence — what this entry teaches, for snippets and dedup}
related:                         # typed cross-refs → the link graph. Each target is another entry's `id`.
  - {slug: {other-entry-id}, rel: relates-to}   # rel: relates-to | child-of | alternative-to | see-also
created: {YYYY-MM-DD}
---

# {Human Readable Title}

{One short paragraph of orientation: when this applies and why it matters. Dense and practical.}

## {Section heading}
{The actual guidance. Reference sibling entries inline as [[other-entry-id]] where it helps a reader
follow the thread — those become links in the graph too.}

## {Section heading}
{…}

> Source: {url} · promoted by {who} · {YYYY-MM-DD}
