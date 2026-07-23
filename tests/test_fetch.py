"""Tests for fetch (cache/error/success/github-raw tier/requests-skip),
extract cascade, http_client (via_urllib/via_wayback/via_github_raw/via_requests),
and _html_to_text."""
import json
from pathlib import Path

import pytest

from helpers import dx, run, _Resp


# ----------------------------------------------------------------- fetch
def test_fetch_cache_hit_no_network(ws, capsys):
    import hashlib
    url = "https://example.com/doc"
    cache = ws / ".devx" / "cache" / "fetch"
    cache.mkdir(parents=True)
    (cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".md")).write_text("cached body text")
    res, _ = run(capsys, "fetch", url)
    assert res["ok"] and res["cached"] is True and "cached body text" in res["text"]


def test_fetch_network_error_is_handled(ws, capsys, monkeypatch):
    from lib.fetch import http_client as hc
    monkeypatch.setattr(dx.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no network")))
    # patch the optional/extra tiers too, so this is deterministically offline even where `requests`
    # is installed (otherwise via_requests would make a real call to nope.invalid).
    monkeypatch.setattr(hc, "via_requests", lambda url: (_ for _ in ()).throw(OSError("no network")))
    monkeypatch.setattr(hc, "via_wayback", lambda url: (_ for _ in ()).throw(OSError("no network")))
    res, _ = run(capsys, "fetch", "https://nope.invalid/x")
    assert res["ok"] is False and "error" in res                 # all tiers fail → ok False


def test_html_to_text_strips_scripts_and_tags():
    out = dx._html_to_text("<html><script>bad()</script><p>Hello <b>World</b></p></html>")
    assert "Hello" in out and "World" in out and "bad()" not in out


def test_fetch_success_extracts_and_caches(ws, capsys, monkeypatch):
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc, "via_urllib", lambda url: "<html><p>Doc Body Here</p></html>")
    res, _ = run(capsys, "fetch", "https://example.com/page")
    assert res["ok"] is True and res["cached"] is False and res["tier"] == "urllib"
    assert "Doc Body Here" in res["text"] and Path(res["path"]).exists()
    res2, _ = run(capsys, "fetch", "https://example.com/page")
    assert res2["cached"] is True                                # second call hits the cache


def test_fetch_github_url_uses_raw_tier(ws, capsys, monkeypatch):
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc, "via_github_raw", lambda url: "raw source")
    res, _ = run(capsys, "fetch", "https://github.com/o/r/blob/main/f.py")
    assert res["ok"] and res["tier"] == "github_raw" and "raw source" in res["text"]


def test_fetch_skips_requests_when_absent_then_wayback(ws, capsys, monkeypatch):
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc, "via_urllib", lambda url: "")          # empty body → next tier
    monkeypatch.setitem(dx.sys.modules, "requests", None)          # import requests → ImportError → skip
    monkeypatch.setattr(hc, "via_wayback", lambda url: "<p>way</p>")
    res, _ = run(capsys, "fetch", "https://example.org/x")
    assert res["ok"] and res["tier"] == "wayback"


# ----------------------------------------------------------------- TTL (F5)
def test_ttl_for_content_classes():
    from lib.fetch.tiers import _ttl_for, DEFAULT_TTL, _DAY
    assert _ttl_for("https://x.dev/CHANGELOG.md") == 1 * _DAY          # changelog → short
    assert _ttl_for("https://github.com/o/r/releases") == 1 * _DAY     # releases → short
    assert _ttl_for("https://www.rfc-editor.org/rfc/rfc9110") == 90 * _DAY   # rfc → long
    assert _ttl_for("https://w3.org/TR/css") == 90 * _DAY              # spec/standard → long
    assert _ttl_for("https://example.com/some/page") == DEFAULT_TTL    # default ~14d


def _age_cache_file(cf, seconds):
    import os
    old = os.stat(cf).st_mtime - seconds
    os.utime(cf, (old, old))


def test_fetch_fresh_cache_hit_no_network(ws, capsys, monkeypatch):
    import hashlib
    from lib.fetch import http_client as hc
    # if the cache were missed this would explode (no tiers succeed); a fresh hit must avoid the network
    monkeypatch.setattr(hc, "via_urllib", lambda url: (_ for _ in ()).throw(AssertionError("network!")))
    url = "https://example.com/stable-doc"
    cache = ws / ".devx" / "cache" / "fetch"
    cache.mkdir(parents=True)
    (cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".md")).write_text("fresh cached body")
    res, _ = run(capsys, "fetch", url)
    assert res["cached"] is True and "fresh cached body" in res["text"]


def test_fetch_stale_cache_refetches(ws, capsys, monkeypatch):
    import hashlib
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc, "via_urllib", lambda url: "<p>fresh network body</p>")
    monkeypatch.setattr(hc, "via_requests", lambda url: (_ for _ in ()).throw(ImportError))
    monkeypatch.setattr(hc, "via_wayback", lambda url: (_ for _ in ()).throw(RuntimeError))
    url = "https://example.com/CHANGELOG"          # short TTL (~1 day)
    cache = ws / ".devx" / "cache" / "fetch"
    cache.mkdir(parents=True)
    cf = cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".md")
    cf.write_text("STALE cached body")
    _age_cache_file(cf, 2 * 86400)                 # 2 days old > 1-day TTL → stale
    res, _ = run(capsys, "fetch", url)
    assert res["cached"] is False and res["tier"] == "urllib"     # re-fetched, not served from cache
    assert "fresh network body" in res["text"] and "STALE" not in res["text"]


def test_fetch_within_ttl_still_hits_even_if_old_but_long_class(ws, capsys, monkeypatch):
    import hashlib
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc, "via_urllib", lambda url: (_ for _ in ()).throw(AssertionError("network!")))
    url = "https://www.rfc-editor.org/rfc/rfc9110"  # long TTL (~90 days)
    cache = ws / ".devx" / "cache" / "fetch"
    cache.mkdir(parents=True)
    cf = cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".md")
    cf.write_text("archived spec body")
    _age_cache_file(cf, 30 * 86400)                # 30 days old < 90-day TTL → still fresh
    res, _ = run(capsys, "fetch", url)
    assert res["cached"] is True and "archived spec body" in res["text"]


def test_fetch_refresh_forces_refetch_even_when_fresh(ws, capsys, monkeypatch):
    import hashlib
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc, "via_urllib", lambda url: "<p>refetched body</p>")
    monkeypatch.setattr(hc, "via_requests", lambda url: (_ for _ in ()).throw(ImportError))
    monkeypatch.setattr(hc, "via_wayback", lambda url: (_ for _ in ()).throw(RuntimeError))
    url = "https://example.com/page"
    cache = ws / ".devx" / "cache" / "fetch"
    cache.mkdir(parents=True)
    (cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".md")).write_text("old body")
    res, _ = run(capsys, "fetch", url, "--refresh")            # fresh entry, but --refresh overrides
    assert res["cached"] is False and "refetched body" in res["text"]


# ----------------------------------------------------------------- http_client
def test_github_blob_to_raw_conversion():
    from lib.fetch import http_client as hc
    assert hc.github_blob_to_raw("https://github.com/psf/requests/blob/main/README.md") \
        == "https://raw.githubusercontent.com/psf/requests/main/README.md"
    assert hc.github_blob_to_raw("https://example.com/not-a-blob") is None


def test_via_github_raw_converts_then_fetches(monkeypatch):
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc, "via_urllib", lambda url: f"RAW {url}")
    assert hc.via_github_raw("https://github.com/o/r/blob/main/f.py") == \
        "RAW https://raw.githubusercontent.com/o/r/main/f.py"
    with pytest.raises(ValueError):
        hc.via_github_raw("https://example.com/not-a-blob")


def test_via_wayback_fetches_closest_snapshot(monkeypatch):
    from lib.fetch import http_client as hc
    cdx = json.dumps({"archived_snapshots": {"closest":
          {"available": True, "url": "http://web.archive.org/snap"}}})

    def fake(req, timeout=None):
        return _Resp(cdx) if "wayback/available" in req.full_url else _Resp("<p>archived body</p>")
    monkeypatch.setattr(hc.urllib.request, "urlopen", fake)
    assert "archived body" in hc.via_wayback("https://gone.example/x")


def test_via_requests_used_when_installed(monkeypatch):
    from lib.fetch import http_client as hc
    fake = type("M", (), {})()
    fake.get = lambda url, headers=None, timeout=None: type(
        "R", (), {"text": "REQ BODY", "raise_for_status": lambda s: None})()
    monkeypatch.setitem(dx.sys.modules, "requests", fake)
    assert hc.via_requests("http://x") == "REQ BODY"


def test_via_wayback_no_snapshot_raises(monkeypatch):
    from lib.fetch import http_client as hc
    monkeypatch.setattr(hc.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(json.dumps({"archived_snapshots": {}})))
    with pytest.raises(RuntimeError):
        hc.via_wayback("https://x/y")


# ----------------------------------------------------------------- extract
def test_extract_markdown_degrades_to_strip():
    from lib.fetch.extract import extract_markdown
    text, method = extract_markdown("<html><script>bad()</script><p>Hello <b>World</b></p></html>")
    assert "Hello" in text and "World" in text and "bad()" not in text
    assert method in ("trafilatura", "beautifulsoup", "strip")   # floor is "strip" when no optional dep


def test_extract_prefers_trafilatura_when_present(monkeypatch):
    from lib.fetch import extract
    fake = type("M", (), {})()
    fake.extract = lambda html, **k: "# Markdown Body"
    monkeypatch.setitem(dx.sys.modules, "trafilatura", fake)
    text, method = extract.extract_markdown("<p>x</p>", "http://u")
    assert method == "trafilatura" and text == "# Markdown Body"


def test_extract_uses_beautifulsoup_when_no_trafilatura(monkeypatch):
    from lib.fetch import extract
    monkeypatch.setitem(dx.sys.modules, "trafilatura", None)     # import trafilatura → ImportError → fall through

    class _Soup:
        def __init__(self, html, parser):
            pass

        def __call__(self, tags):
            return []

        def get_text(self, sep):
            return "BS4 TEXT"
    fake_bs4 = type("M", (), {})()
    fake_bs4.BeautifulSoup = _Soup
    monkeypatch.setitem(dx.sys.modules, "bs4", fake_bs4)
    text, method = extract.extract_markdown("<p>x</p>")
    assert method == "beautifulsoup" and "BS4 TEXT" in text


def test_extract_falls_through_on_extractor_errors(monkeypatch):
    from lib.fetch import extract
    boom = type("M", (), {})(); boom.extract = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    monkeypatch.setitem(dx.sys.modules, "trafilatura", boom)
    bad_bs4 = type("M", (), {})(); bad_bs4.BeautifulSoup = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("y"))
    monkeypatch.setitem(dx.sys.modules, "bs4", bad_bs4)
    text, method = extract.extract_markdown("<p>Hello</p>")
    assert method == "strip" and "Hello" in text                 # both richer extractors raised → floor
