"""Tests for chunker, FTS search, ripgrep search, kb_search, index, sanitize,
_build_index, project-scope, and the fts5_available misc check."""
import pytest

from helpers import dx, run, requires_fts5, requires_rg


# ----------------------------------------------------------------- chunker
def test_chunk_breadcrumb_and_sibling_headings():
    md = "# Title\nintro\n## Sub A\nbody a\n## Sub B\nbody b\n"
    crumbs = [c for c, _ in dx._chunk_markdown("notes.md", md)]
    assert "notes.md > Title" in crumbs
    assert "notes.md > Title > Sub A" in crumbs
    assert "notes.md > Title > Sub B" in crumbs
    assert "notes.md > Title > Sub A > Sub B" not in crumbs  # siblings, not nested


def test_chunk_no_headings_is_single_chunk():
    chunks = dx._chunk_markdown("flat.md", "just text\nmore text")
    assert len(chunks) == 1 and chunks[0][0] == "flat.md"


def test_chunk_deeper_then_shallower_pops_stack():
    crumbs = [c for c, _ in dx._chunk_markdown("x.md", "# A\n## B\n### C\ncbody\n## D\ndbody\n")]
    assert "x.md > A > D" in crumbs
    assert "x.md > A > B > C > D" not in crumbs


# --------------------------------------------------------------- sanitize
def test_sanitize_quotes_tokens():
    assert dx._sanitize("CVE-2021-1234 foo/bar") == '"CVE" "2021" "1234" "foo" "bar"'


def test_sanitize_drops_punctuation_only():
    assert dx._sanitize("!!!") == ""


# ------------------------------------------------------------------ index
@requires_fts5
def test_index_build_incremental_and_prune(ws):
    v = ws / "vault"
    (v / "a.md").write_text("# A\nalpha content\n")
    (v / "b.md").write_text("# B\nbeta content\n")
    s1 = dx._build_index(dx.db_path(), dx._vault_items())
    assert s1["files"] == 2 and s1["changed"] == 2 and s1["chunks"] >= 2

    s2 = dx._build_index(dx.db_path(), dx._vault_items())   # nothing changed
    assert s2["changed"] == 0 and s2["files"] == 2

    (v / "a.md").write_text("# A\nalpha content changed\n")  # one file changed
    assert dx._build_index(dx.db_path(), dx._vault_items())["changed"] == 1

    (v / "b.md").unlink()                                    # one file removed -> pruned
    assert dx._build_index(dx.db_path(), dx._vault_items())["files"] == 1


@requires_fts5
def test_cmd_index_scopes(ws, capsys):
    (ws / "vault" / "x.md").write_text("# X\nx\n")
    (ws / ".devx" / "project.md").write_text("# Project\nstack\n")
    res, _ = run(capsys, "index", "--scope", "all")
    assert res["ok"] and res["vault"]["files"] == 1 and res["project"]["files"] == 1


def test_project_items_includes_learnings_index(ws):
    (ws / ".devx" / "learnings-index.md").write_text("# Patterns\n## P1\nflaky tests\n")
    (ws / ".devx" / "learnings.md").write_text("# learnings\nx\n")
    rels = [rel for rel, _ in dx._project_items()]
    assert "learnings-index.md" in rels and "learnings.md" in rels


def test_learnings_index_is_in_project_top():
    assert "learnings-index.md" in dx.PROJECT_TOP


def test_project_items_includes_phase_research_and_summary(ws):
    # JIT phase loop: per-phase research + summaries must be indexed so they rank for the next phase.
    ph = ws / ".devx" / "workstreams" / "w" / "phases" / "01-x"
    (ph / "research").mkdir(parents=True)
    (ph / "research" / "r.md").write_text("# R\nfindings on approach A\n")
    (ph / "summary.md").write_text("# Phase 01 summary\ndelivered X; reusable: foo()\n")
    rels = [rel for rel, _ in dx._project_items()]
    assert "workstreams/w/phases/01-x/research/r.md" in rels
    assert "workstreams/w/phases/01-x/summary.md" in rels


def test_vault_items_excludes_readme_and_index_stubs(ws):
    v = ws / "vault"
    (v / "README.md").write_text("# DevX Vault\nmeta doc about the vault index and query\n")
    (v / "patterns").mkdir()
    (v / "patterns" / "_index.md").write_text("# Patterns\ncategory stub\n")
    (v / "patterns" / "real.md").write_text("# Real Entry\nactual knowledge\n")
    rels = [rel for rel, _ in dx._vault_items()]
    assert rels == ["patterns/real.md"]                  # README + _index stubs are navigation, not knowledge


@requires_fts5
def test_kb_search_does_not_return_readme_or_index_stub(ws, capsys):
    v = ws / "vault"
    (v / "README.md").write_text("# DevX Vault\nthe vault index, query, and search live here\n")
    (v / "patterns").mkdir()
    (v / "patterns" / "_index.md").write_text("# Patterns\nindex query search category\n")
    (v / "patterns" / "di.md").write_text("# Dependency Injection\nconstructor injection query search\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "kb_search", "index query search", "--scope", "vault")
    paths = {r["path"] for r in res["results"]}
    assert "README.md" not in paths and "patterns/_index.md" not in paths


@requires_fts5
@requires_rg
def test_kb_search_thin_vault_no_cross_tier_path_dupes(ws, capsys):
    # In a thin vault, FTS (<3 hits) triggers the ripgrep fallback. The same doc must not appear twice
    # (fts5 vault-relative path vs ripgrep absolute path), and fallback paths must be vault-relative.
    (ws / "vault" / "only.md").write_text("# Only Doc\nuniquetoken alpha beta gamma\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "kb_search", "uniquetoken", "--scope", "vault")
    paths = [r["path"] for r in res["results"]]
    assert paths.count("only.md") == 1                  # collapsed across the fts5 + ripgrep tiers
    assert all(not p.startswith("/") for p in paths)    # fallback paths normalized to vault-relative


# ----------------------------------------------------------- link graph
def test_extract_links_related_block_and_wikilinks():
    text = ("---\nid: my-doc\ntitle: My Doc\n"
            "related:\n  - {slug: backoff-jitter, rel: relates-to}\n"
            "  - {slug: retry-storms, rel: child-of}\n---\n"
            "# My Doc\nSee [[idempotency-keys]] and [[circuit-breaker|breakers]].\n")
    assert dx._extract_links(text) == {
        "backoff-jitter", "retry-storms", "idempotency-keys", "circuit-breaker"}


def test_extract_links_inline_related_list():
    assert dx._extract_links("---\nrelated: [alpha, beta]\n---\n# T\nbody\n") == {"alpha", "beta"}


def test_extract_links_none_when_absent():
    assert dx._extract_links("# Plain\nno links, no frontmatter\n") == set()


@requires_fts5
def test_index_builds_and_prunes_links_graph(ws):
    v = ws / "vault"
    (v / "a.md").write_text("# A\nrelated body\nSee [[b-doc]] and [[c-doc]].\n")
    s1 = dx._build_index(dx.db_path(), dx._vault_items())
    assert s1["links"] == 2                                   # [[b-doc]], [[c-doc]]

    (v / "a.md").write_text("# A\nshrunk\nSee [[b-doc]] only.\n")   # changed → links replaced, not doubled
    assert dx._build_index(dx.db_path(), dx._vault_items())["links"] == 1

    (v / "a.md").unlink()                                     # pruned → its links go too
    assert dx._build_index(dx.db_path(), dx._vault_items())["links"] == 0


# ----------------------------------------------------- index-backed meta (F1)
@requires_fts5
def test_index_populates_and_counts_meta(ws):
    v = ws / "vault"
    (v / "fm.md").write_text(
        "---\nid: my-doc\ntitle: Canonical Title\ntags: a, b\nsummary: a crisp summary\n---\n"
        "# A Different H1\nbody paragraph\n")
    (v / "plain.md").write_text("# Plain Heading\nfirst real paragraph here\n")
    s = dx._build_index(dx.db_path(), dx._vault_items())
    assert s["meta"] == 2                                      # one meta row per indexed file

    titles = dx.meta_titles(dx.db_path())
    assert titles[dx.norm_title("Canonical Title")] == "fm.md"   # frontmatter title wins over H1
    assert titles[dx.norm_title("Plain Heading")] == "plain.md"  # falls back to the H1

    slugs = dx.meta_slugs(dx.db_path())
    assert "my-doc" in slugs and "fm" in slugs                 # frontmatter id + filename stem
    assert "plain" in slugs                                    # stem when no frontmatter id


@requires_fts5
def test_meta_pruned_with_file(ws):
    v = ws / "vault"
    (v / "a.md").write_text("# A\nalpha\n")
    (v / "b.md").write_text("# B\nbeta\n")
    assert dx._build_index(dx.db_path(), dx._vault_items())["meta"] == 2
    (v / "b.md").unlink()
    assert dx._build_index(dx.db_path(), dx._vault_items())["meta"] == 1   # meta pruned with the file


def test_meta_helpers_empty_when_no_db(ws):
    assert dx.meta_titles(ws / "nope.sqlite") == {} and dx.meta_slugs(ws / "nope.sqlite") == set()


def test_doc_meta_extracts_title_id_tags_summary():
    text = ("---\nid: x-id\ntitle: X Title\ntags: t1, t2\n---\n# Other\nthe first body line\n")
    title, doc_id, tags, summary = dx._doc_meta(text, "sub/x.md")
    assert title == "X Title" and doc_id == "x-id" and "t1" in tags and summary == "the first body line"
    # no frontmatter id → filename stem; no frontmatter title → H1
    t2, id2, _, _ = dx._doc_meta("# Heading One\nbody\n", "dir/note.md")
    assert t2 == "Heading One" and id2 == "note"


# ------------------------------------------------------------- fts search
@requires_fts5
def test_fts_search_returns_none_when_db_missing(ws):
    assert dx._fts_search("anything", 5, ws / "nope.sqlite", "fts5:vault") is None


@requires_fts5
def test_fts_search_ranks_real_hits(ws):
    (ws / "vault" / "rate.md").write_text("# Rate Limiting\nToken bucket limiter handles bursts.\n")
    dx._build_index(dx.db_path(), dx._vault_items())
    hits = dx._fts_search("token bucket bursts", 5, dx.db_path(), "fts5:vault")
    assert hits and any(h["path"] == "rate.md" for h in hits)
    assert all(h["tier"] == "fts5:vault" for h in hits)


# -------------------------------------------------------------- rg search
@requires_rg
def test_rg_search_is_whole_word_only(ws):
    v = ws / "vault"
    (v / "noise.md").write_text("# Curated strategies\nNothing relevant here.\n")
    (v / "real.md").write_text("# Rate\nThe rate limiter.\n")
    paths = {h["path"] for h in dx._rg_search("rate", [v], 10, "ripgrep:vault")}
    assert any("real.md" in p for p in paths)
    assert not any("noise.md" in p for p in paths)   # 'rate' must not match inside 'Curated'


# -------------------------------------------------------------- kb_search
@requires_fts5
def test_kb_search_scope_vault(ws, capsys):
    (ws / "vault" / "di.md").write_text("# Dependency Injection\nConstructor injection decouples wiring.\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, code = run(capsys, "kb_search", "constructor injection", "--scope", "vault")
    assert code == 0 and res["count"] >= 1
    assert any(r["path"] == "di.md" for r in res["results"])
    assert res["tiers"][0].startswith("fts5")


@requires_fts5
def test_kb_search_scope_all_ranks_fts_first(ws, capsys):
    (ws / "vault" / "vaultdoc.md").write_text("# Idempotency\nUse idempotency keys for safe retries.\n")
    (ws / ".devx" / "learnings.md").write_text("# learnings\nidempotency keys prevent dupes.\n")
    dx.main(["index", "--scope", "all"]); capsys.readouterr()
    res, code = run(capsys, "kb_search", "idempotency keys", "--scope", "all")
    assert code == 0 and res["results"][0]["tier"].startswith("fts5")


@requires_fts5
def test_kb_search_needs_web_when_thin(ws, capsys):
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "kb_search", "nonexistent zxqw topic")
    assert res["needs_web"] is True and res["count"] < dx.MIN_LOCAL_RESULTS


# ----------------------------------------------------- graph-walk (F3)
@requires_fts5
def test_kb_search_appends_graph_neighbor_via_wikilink(ws, capsys):
    v = ws / "vault"
    # A links to b-doc (a [[wikilink]]); B exists with id b-doc. A search hitting A should also
    # surface B as a graph neighbor (tier=="graph", via=="a.md").
    (v / "a.md").write_text("# Retry Storms\nThundering retries overwhelm a service. See [[b-doc]].\n")
    (v / "b.md").write_text("---\nid: b-doc\ntitle: Backoff Jitter\n---\n# Backoff Jitter\nAdd jitter to backoff.\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "kb_search", "thundering retries overwhelm", "--scope", "vault")
    by_path = {r["path"]: r for r in res["results"]}
    assert "a.md" in by_path                                   # primary hit
    assert "b.md" in by_path and by_path["b.md"]["tier"] == "graph"
    assert by_path["b.md"]["via"] == "a.md"                    # walked from A's outgoing link
    assert by_path["b.md"]["section"] is None
    assert "graph:vault" in res["tiers"]


@requires_fts5
def test_kb_search_graph_resolves_via_related_slug(ws, capsys):
    v = ws / "vault"
    # frontmatter `related:` slug (not a wikilink) also drives the walk; resolves by filename stem
    (v / "a.md").write_text(
        "---\nrelated:\n  - {slug: neighbor, rel: relates-to}\n---\n# Cache Stampede\nMany misses at once.\n")
    (v / "neighbor.md").write_text("# Request Coalescing\nCollapse duplicate in-flight requests.\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "kb_search", "many misses at once", "--scope", "vault")
    nb = {r["path"]: r for r in res["results"]}
    assert nb.get("neighbor.md", {}).get("tier") == "graph" and nb["neighbor.md"]["via"] == "a.md"


@requires_fts5
def test_kb_search_no_graph_neighbor_when_no_links(ws, capsys):
    (ws / "vault" / "lonely.md").write_text("# Standalone Topic\nNo outgoing links at all here.\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "kb_search", "standalone topic", "--scope", "vault")
    assert not any(r["tier"] == "graph" for r in res["results"])
    assert "graph:vault" not in res["tiers"]


@requires_fts5
def test_kb_search_graph_neighbor_not_duplicated_when_already_a_hit(ws, capsys):
    v = ws / "vault"
    # both A and B match the query AND A links to B → B must appear once (as a real hit, not re-added)
    (v / "a.md").write_text("# Idempotency Keys\nUse idempotency keys. See [[b-doc]].\n")
    (v / "b.md").write_text("---\nid: b-doc\n---\n# Idempotency Tokens\nIdempotency keys prevent dupes.\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "kb_search", "idempotency keys", "--scope", "vault")
    b_rows = [r for r in res["results"] if r["path"] == "b.md"]
    assert len(b_rows) == 1 and b_rows[0]["tier"] != "graph"   # surfaced as a primary hit, not a neighbor


# --- H-05: deleted file's chunks never resurface (rowid-reuse misattribution) ---
@requires_fts5
def test_index_delete_then_readd_no_resurface(ws, capsys):
    v = ws / "vault"
    (v / "a.md").write_text("# A\nalpha aaa\n")
    (v / "b.md").write_text("# B\nbeta deletedterm\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    (v / "b.md").unlink()
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()       # prune b.md
    (v / "c.md").write_text("# C\ngamma ccc\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()       # c.md may reuse b.md's rowid
    res, _ = run(capsys, "kb_search", "deletedterm", "--scope", "vault")
    assert res["count"] == 0                                          # the deleted term is truly gone


@requires_fts5
def test_index_update_prune_and_project_scope(ws, capsys):
    v = ws / "vault"
    (v / "a.md").write_text("# A\nalpha\n")
    run(capsys, "index", "--scope", "vault")
    (v / "a.md").write_text("# A\nalpha updated\n")               # changed → update-existing path
    run(capsys, "index", "--scope", "vault")
    (v / "a.md").unlink()                                          # deleted → prune path
    res, _ = run(capsys, "index", "--scope", "vault")
    assert res["vault"]["files"] == 0
    (ws / ".devx" / "research").mkdir(parents=True, exist_ok=True)
    (ws / ".devx" / "research" / "r.md").write_text("# R\nnote\n")
    (ws / ".devx" / "decisions.md").write_text("# D\nchose x\n")
    res, _ = run(capsys, "index", "--scope", "project")           # _project_items globs + project scope
    assert res["project"]["files"] >= 1


@requires_rg
def test_kb_search_ripgrep_fallback_when_no_index(ws, capsys):
    (ws / "vault" / "k.md").write_text("# K\nfindme unique token here\n")   # vault doc, no FTS index built
    res, _ = run(capsys, "kb_search", "findme")
    assert any("ripgrep" in t for t in res["tiers"])              # no DB → cascade degrades to ripgrep
    assert any("k.md" in r.get("path", "") for r in res["results"])
