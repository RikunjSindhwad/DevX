"""Tests for validate gate, _check_url_live, _parse_iso_date, _extract_urls,
and promotion (CLI gate)."""
import datetime

from helpers import dx, run, GOOD, _v, _Resp


# ----------------------------------------------------- validate (helpers)
def test_extract_urls_dedup_and_strip_punctuation():
    urls = dx._extract_urls("see https://a.com/x. and https://a.com/x again, https://b.org)")
    assert urls == ["https://a.com/x", "https://b.org"]


def test_parse_iso_date():
    assert dx._parse_iso_date("foo 2026-06-20 bar") == datetime.date(2026, 6, 20)
    assert dx._parse_iso_date("no date here") is None


# ----------------------------------------------- validate_promotion (pure)
def test_validate_pass_with_live_url():
    assert _v(GOOD)["verdict"] == "pass"


def test_validate_fail_missing_provenance():
    res = _v("# T\n\nbody only\n")
    assert res["verdict"] == "fail"
    assert any(c["check"] == "provenance" and not c["ok"] for c in res["checks"])


def test_validate_fail_on_dead_link_is_stale_reference():
    res = _v(GOOD, url_checker=lambda u: ("dead", 404))
    assert res["verdict"] == "fail" and res["stale_refs"] == ["https://ex.com/a"]


def test_validate_unknown_url_warns_not_fails():
    res = _v(GOOD, url_checker=lambda u: ("unknown", "timeout"))
    assert res["verdict"] == "pass"
    assert any(w["warn"] == "url-unreachable" for w in res["warnings"])


def test_validate_stale_by_age_warns():
    res = _v(GOOD, today=datetime.date(2030, 1, 1))
    assert res["verdict"] == "pass"
    assert any(w["warn"] == "stale-by-age" for w in res["warnings"])


def test_validate_dedup_by_title():
    res = _v(GOOD, vault_titles={"topic title": "patterns/topic.md"})
    assert res["verdict"] == "fail" and res["duplicate"] == "patterns/topic.md"


def test_validate_dedup_by_filename():
    res = _v(GOOD, vault_titles={"other": "patterns/topic-title.md"},
             target_rel="patterns/topic-title.md")
    assert res["duplicate"] == "patterns/topic-title.md"


def test_validate_dedup_uses_frontmatter_title_over_h1():
    text = ("---\ntitle: Canonical Name\n---\n# A Different H1\n\nbody\n\n"
            "> Source: https://ex.com/a · by x · 2026-06-20\n")
    res = _v(text, vault_titles={"canonical name": "patterns/canonical.md"})
    assert res["verdict"] == "fail" and res["duplicate"] == "patterns/canonical.md"


def test_validate_dangling_links_warn_not_fail():
    res = _v(GOOD + "\nfurther: [[unknown-thing]] and [[another-missing]].\n")
    assert res["verdict"] == "pass"                          # dangling = nudge, never a block
    assert res["dangling_links"] == ["another-missing", "unknown-thing"]   # sorted
    assert any(w["warn"] == "dangling-links" and "unknown-thing" in w["detail"]
               for w in res["warnings"])


def test_validate_links_resolve_via_slugs_and_titles():
    # one link resolves by slug, the other by an existing vault filename stem → no dangling warning
    res = _v(GOOD + "\nsee [[known-slug]] and [[topic]].\n",
             vault_slugs={"known-slug"}, vault_titles={"x": "patterns/topic.md"})
    assert res["dangling_links"] == [] and not any(
        w["warn"] == "dangling-links" for w in res["warnings"])


def test_path_prefixed_wikilink_resolves_by_basename():
    # [[category/slug]] resolves via its basename — not flagged dangling (issue #3: path-prefixed wikilinks)
    res = _v(GOOD + "\nsee [[patterns/problem-solving-techniques]].\n",
             vault_slugs={"problem-solving-techniques"})
    assert res["dangling_links"] == [] and not any(
        w["warn"] == "dangling-links" for w in res["warnings"])


def test_validate_flags_absolute_path_leak(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _v(GOOD + f"\nsee {tmp_path}/secret for details\n")
    assert res["verdict"] == "fail"
    assert any(c["check"] == "generalized" and not c["ok"] for c in res["checks"])


# ------------------------------------------------------ validate (CLI gate)
def test_cli_validate_offline_pass_exit0(ws, capsys):
    (ws / "cand.md").write_text(GOOD)
    res, code = run(capsys, "validate", "cand.md", "--offline")
    assert code == 0 and res["verdict"] == "pass"


def test_cli_validate_missing_provenance_exit1(ws, capsys):
    (ws / "cand.md").write_text("# T\nbody\n")
    res, code = run(capsys, "validate", "cand.md", "--offline")
    assert code == 1 and res["ok"] is False


def test_cli_validate_promote_writes_then_dedup_blocks_then_update_waives(ws, capsys):
    (ws / "cand.md").write_text(
        "# Backoff Jitter\nbody\n\n> Source: https://ex.com/a · auto-promoted by researcher · 2026-06-20\n")
    target = "patterns/backoff-jitter.md"

    res, code = run(capsys, "validate", "cand.md", "--promote-to", target, "--offline")
    assert code == 0 and res.get("promoted") is True
    assert (ws / "vault" / "patterns" / "backoff-jitter.md").exists()

    res2, code2 = run(capsys, "validate", "cand.md", "--promote-to", target, "--offline")
    assert code2 == 1 and res2.get("promoted") is False          # dedup blocks the second write

    res3, code3 = run(capsys, "validate", "cand.md", "--promote-to", target, "--offline", "--update")
    assert code3 == 0 and res3.get("promoted") is True           # --update waives only dedup


def test_cli_validate_promote_blocked_by_dead_link(ws, capsys, monkeypatch):
    monkeypatch.setattr(dx.validate, "_check_url_live", lambda u, timeout=15: ("dead", 404))
    (ws / "cand.md").write_text(
        "# Dead Ref\nbody\n\n> Source: https://gone.example/x · auto-promoted by researcher · 2026-06-20\n")
    res, code = run(capsys, "validate", "cand.md", "--promote-to", "patterns/dead-ref.md")
    assert code == 1 and res.get("promoted") is False
    assert not (ws / "vault" / "patterns" / "dead-ref.md").exists()  # nothing written on fail


# --- H-02 (traversal) ---
def test_cli_validate_promote_to_rejects_traversal(ws, capsys):
    (ws / "cand.md").write_text(GOOD)
    res, code = run(capsys, "validate", str(ws / "cand.md"), "--promote-to", "../escaped.md", "--offline")
    assert code == 1 and res.get("promoted") is False and "escape" in res.get("error", "").lower()
    assert not (ws / "escaped.md").exists()          # vault is ws/vault → ../ would land in ws


def test_cli_validate_promote_to_rejects_absolute(ws, capsys):
    (ws / "cand.md").write_text(GOOD)
    res, code = run(capsys, "validate", str(ws / "cand.md"), "--promote-to", "/tmp/devx_abs_escape.md", "--offline")
    assert code == 1 and res.get("promoted") is False
    assert not __import__("pathlib").Path("/tmp/devx_abs_escape.md").exists()


# ---- lib/validate coverage ----
def test_check_url_live_classifies_live_dead_unknown(monkeypatch):
    from lib import validate as v
    monkeypatch.setattr(v.urllib.request, "urlopen", lambda *a, **k: _Resp("ok", 200))
    assert v._check_url_live("http://x")[0] == "live"

    def http_err(code):
        def f(*a, **k):
            raise dx.urllib.error.HTTPError("http://x", code, "msg", None, None)
        return f
    monkeypatch.setattr(v.urllib.request, "urlopen", http_err(404))
    assert v._check_url_live("http://x")[0] == "dead"            # 404/410 = stale reference
    monkeypatch.setattr(v.urllib.request, "urlopen", http_err(500))
    assert v._check_url_live("http://x")[0] == "unknown"         # transient → never fails a promotion


def test_parse_iso_date_invalid():
    from lib import validate as v
    assert v._parse_iso_date("2026-13-40") is None and v._parse_iso_date("no date") is None


def test_check_url_live_head_refused_then_get(monkeypatch):
    from lib import validate as v

    def live_on_get(req, timeout=None):
        if getattr(req, "method", "") == "HEAD":
            raise dx.urllib.error.HTTPError("u", 403, "no", None, None)
        return _Resp("ok", 200)
    monkeypatch.setattr(v.urllib.request, "urlopen", live_on_get)
    assert v._check_url_live("http://x")[0] == "live"            # HEAD refused → GET retry → live

    def dead_on_get(req, timeout=None):
        if getattr(req, "method", "") == "HEAD":
            raise dx.urllib.error.HTTPError("u", 405, "no", None, None)
        raise dx.urllib.error.HTTPError("u", 404, "gone", None, None)
    monkeypatch.setattr(v.urllib.request, "urlopen", dead_on_get)
    assert v._check_url_live("http://x")[0] == "dead"           # HEAD refused → GET 404 → dead


def test_cli_validate_resolves_links_against_real_vault(ws, capsys):
    # drives the real _vault_slugs()/_vault_titles() readers: a link to an existing doc's
    # frontmatter `id` resolves; a link to a missing slug surfaces as a dangling-links warning.
    (ws / "vault" / "patterns").mkdir(parents=True, exist_ok=True)
    (ws / "vault" / "patterns" / "retries.md").write_text(
        "---\nid: retry-backoff\ntitle: Retry Backoff\n---\n# Retry Backoff\nbody\n")
    (ws / "cand.md").write_text(
        "# Idempotency Keys\nbody\nfurther: [[retry-backoff]] and [[does-not-exist]].\n\n"
        "> Source: https://ex.com/a · by x · 2026-06-20\n")
    res, code = run(capsys, "validate", "cand.md", "--offline")
    assert code == 0                                          # dangling links never block
    assert res["dangling_links"] == ["does-not-exist"]       # retry-backoff resolved via frontmatter id


# ----------------------------------------- F1: index-backed dedup metadata
from helpers import requires_fts5


@requires_fts5
def test_vault_titles_and_slugs_read_from_index(ws):
    v = ws / "vault"
    (v / "retries.md").write_text(
        "---\nid: retry-backoff\ntitle: Retry Backoff\n---\n# Retry Backoff\nbody\n")
    dx._build_index(dx.db_path(), dx._vault_items())
    # reads come from the meta table now (the index exists), not a file scan
    assert dx._vault_titles() == {dx.norm_title("Retry Backoff"): "retries.md"}
    slugs = dx._vault_slugs()
    assert "retry-backoff" in slugs and "retries" in slugs


@requires_fts5
def test_index_backed_dedup_blocks_promotion(ws, capsys):
    # promote once (builds the index), then a same-title candidate is blocked by index-backed dedup
    (ws / "cand.md").write_text(
        "# Token Bucket\nbody\n\n> Source: https://ex.com/a · by x · 2026-06-20\n")
    res1, code1 = run(capsys, "validate", "cand.md", "--promote-to", "patterns/token-bucket.md", "--offline")
    assert code1 == 0 and res1.get("promoted") is True
    (ws / "dup.md").write_text(
        "# Token Bucket\ndifferent body\n\n> Source: https://ex.com/b · by y · 2026-06-20\n")
    res2, code2 = run(capsys, "validate", "dup.md", "--offline")
    assert any(c["check"] == "dedup" and not c["ok"] for c in res2["checks"])
    assert res2["duplicate"] == "patterns/token-bucket.md"   # came from the index meta table


def test_vault_titles_file_scan_fallback_when_no_index(ws, monkeypatch):
    # force the no-index path: _vault_titles must still work via the file scan
    monkeypatch.setattr(dx.validate.probes, "fts5_available", lambda: False)
    v = ws / "vault"
    (v / "patterns").mkdir(parents=True, exist_ok=True)
    (v / "patterns" / "x.md").write_text("---\nid: x-id\ntitle: Scanned Title\n---\n# H\nbody\n")
    assert dx._vault_titles() == {dx.norm_title("Scanned Title"): "patterns/x.md"}
    slugs = dx._vault_slugs()
    assert "x-id" in slugs and "x" in slugs                   # frontmatter id + stem, from the scan


# ----------------------------------------- F2: fuzzy near-duplicate warning
@requires_fts5
def test_near_duplicate_warns_on_same_topic_different_title(ws, capsys):
    v = ws / "vault"
    (v / "patterns").mkdir(parents=True, exist_ok=True)
    (v / "patterns" / "token-bucket.md").write_text(
        "---\ntitle: Token Bucket Rate Limiting\nsummary: token bucket limiter smooths bursty traffic\n---\n"
        "# Token Bucket Rate Limiting\nA token bucket limiter smooths bursty request traffic with refill.\n")
    dx._build_index(dx.db_path(), dx._vault_items())
    # a DIFFERENT title on the same topic → exact dedup misses it, fuzzy near-dup should warn
    (ws / "cand.md").write_text(
        "---\ntitle: Leaky Bucket Throttling\nsummary: token bucket limiter smooths bursty traffic\n---\n"
        "# Leaky Bucket Throttling\nA token bucket limiter smooths bursty request traffic with refill.\n\n"
        "> Source: https://ex.com/a · by x · 2026-06-20\n")
    res, code = run(capsys, "validate", "cand.md", "--offline")
    assert code == 0                                              # near-dup is a WARNING, never a block
    assert "patterns/token-bucket.md" in res["near_duplicates"]
    assert any(w["warn"] == "thematic-overlap" and "token-bucket.md" in w["detail"]
               for w in res["warnings"])


@requires_fts5
def test_no_near_duplicate_for_unrelated_note(ws, capsys):
    v = ws / "vault"
    (v / "patterns").mkdir(parents=True, exist_ok=True)
    (v / "patterns" / "token-bucket.md").write_text(
        "---\ntitle: Token Bucket Rate Limiting\nsummary: token bucket limiter smooths bursty traffic\n---\n"
        "# Token Bucket Rate Limiting\nA token bucket limiter smooths bursty request traffic.\n")
    dx._build_index(dx.db_path(), dx._vault_items())
    (ws / "cand.md").write_text(
        "---\ntitle: Database Index Maintenance\nsummary: vacuum and reindex postgres tables routinely\n---\n"
        "# Database Index Maintenance\nRun vacuum and reindex on postgres tables to reclaim bloat.\n\n"
        "> Source: https://ex.com/a · by x · 2026-06-20\n")
    res, code = run(capsys, "validate", "cand.md", "--offline")
    assert code == 0 and res["near_duplicates"] == []
    assert not any(w["warn"] == "thematic-overlap" for w in res["warnings"])


@requires_fts5
def test_thematic_overlap_suppressed_when_candidate_crosslinks(ws, capsys):
    # complementary entries that DELIBERATELY cross-link must not be flagged (issue #4: sibling, not twin)
    v = ws / "vault"
    (v / "patterns").mkdir(parents=True, exist_ok=True)
    (v / "patterns" / "token-bucket.md").write_text(
        "---\nid: token-bucket\ntitle: Token Bucket Rate Limiting\nsummary: token bucket limiter smooths bursty traffic\n---\n"
        "# Token Bucket Rate Limiting\nA token bucket limiter smooths bursty request traffic with refill.\n")
    dx._build_index(dx.db_path(), dx._vault_items())
    (ws / "cand.md").write_text(                                  # same topic, but cross-links token-bucket
        "---\ntitle: Leaky Bucket Throttling\nsummary: token bucket limiter smooths bursty traffic\n"
        "related:\n  - {slug: token-bucket, rel: relates-to}\n---\n"
        "# Leaky Bucket Throttling\nA token bucket limiter smooths bursty request traffic with refill.\n\n"
        "> Source: https://ex.com/a · by x · 2026-06-20\n")
    res, code = run(capsys, "validate", "cand.md", "--offline")
    assert code == 0 and res["near_duplicates"] == []            # cross-linked → complementary, suppressed
    assert not any(w["warn"] == "thematic-overlap" for w in res["warnings"])


@requires_fts5
def test_exact_duplicate_does_not_also_emit_near_duplicate(ws, capsys):
    # when the exact dedup check already fires, the fuzzy pass is skipped (no double-flag)
    (ws / "cand.md").write_text(
        "# Backoff Jitter\nbody about backoff jitter retries\n\n> Source: https://ex.com/a · by x · 2026-06-20\n")
    run(capsys, "validate", "cand.md", "--promote-to", "patterns/backoff-jitter.md", "--offline")
    res, _ = run(capsys, "validate", "cand.md", "--offline")
    assert res["duplicate"] == "patterns/backoff-jitter.md"      # exact dedup fires
    assert res["near_duplicates"] == []                          # fuzzy pass skipped


def test_validate_soft_warnings(ws, capsys):
    (ws / "c.md").write_text("# T\nbody\n> Source: https://ex.com/a · by x · 2000-01-01\n"
                             "see notes in .devx/ here\n")
    res, _ = run(capsys, "validate", "c.md", "--offline")
    warns = " ".join(w["warn"] for w in res["warnings"])
    assert "stale-by-age" in warns and "project-specifics" in warns
