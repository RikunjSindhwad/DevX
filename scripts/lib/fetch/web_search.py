"""Multi-engine web search with reciprocal-rank-fusion (RRF) dedupe.

DuckDuckGo, Bing, and Yahoo are queried by default; callers may explicitly select a subset with
``engines=[...]``. Results are fused and deduplicated so failure or markup drift in one provider does
not make it the only retrieval path. Network uses module-qualified urllib so test patches still
intercept.
"""
from __future__ import annotations

import base64
import re
import urllib.parse
import urllib.request

from .extract import html_to_text

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BROWSER_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8",
}
_DEFAULT_ENGINES = ["duckduckgo", "bing", "yahoo"]


def _request(url: str, *, referer: str | None = None):
    headers = dict(_BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _unwrap_ddg_url(href: str) -> str:
    if not href:
        return href
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/?" in href:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        return urllib.parse.unquote(qs.get("uddg", [href])[0])
    return href


def _unwrap_bing_url(href: str) -> str:
    if not href:
        return href
    if "bing.com/ck/a" not in href:
        return href
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        vals = qs.get("u", [])
        if not vals:
            return href
        u = vals[0]
        if u.startswith("a1"):
            u = u[2:]
        u += "=" * ((-len(u)) % 4)
        return base64.urlsafe_b64decode(u).decode("utf-8", "replace").strip()
    except Exception:
        return href


def _unwrap_yahoo_url(href: str) -> str:
    if not href:
        return href
    try:
        parsed = urllib.parse.urlparse(href)
        if "r.search.yahoo.com" in parsed.netloc or "/RU=" in parsed.path:
            parts = parsed.path.split("/RU=")
            if len(parts) > 1:
                return urllib.parse.unquote(parts[1].split("/")[0])
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ("RU", "u", "url"):
            if key in qs:
                return urllib.parse.unquote(qs[key][0])
    except Exception:
        pass
    return href


def _extract_first(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.I | re.S)
    return m.group(1).strip() if m else ""


def _ddg(query: str, limit: int):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query, "kl": "us-en"})
    html = _request(url, referer="https://duckduckgo.com/")
    blocks = re.findall(r'<div[^>]*class="[^"]*\bresult\b(?![^"]*\bresult--ad\b)[^"]*"[^>]*>(.*?)'
                        r'(?=<div[^>]*class="[^"]*\bresult\b|\Z)', html, re.I | re.S)
    out = []
    for block in blocks:
        link = re.search(r'<a[^>]*class="[^"]*\bresult__a\b[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                         block, re.I | re.S)
        if not link:
            continue
        href = _unwrap_ddg_url(link.group(1))
        title = html_to_text(link.group(2))
        snippet = html_to_text(_extract_first(r'<a[^>]*class="[^"]*\bresult__snippet\b[^"]*"[^>]*>(.*?)</a>',
                                              block))
        if href and title:
            out.append({"url": href, "title": title, "snippet": snippet})
        if len(out) >= limit:
            break
    return out


def _bing(query: str, limit: int):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"q": query, "setlang": "en-US", "cc": "US"}
    )
    html = _request(url, referer="https://www.bing.com/")
    blocks = re.findall(r'<li[^>]*class="[^"]*\bb_algo\b[^"]*"[^>]*>(.*?)'
                        r'(?=<li[^>]*class="[^"]*\bb_algo\b|\Z)', html, re.I | re.S)
    out = []
    for block in blocks:
        link = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.I | re.S)
        if not link:
            continue
        href = _unwrap_bing_url(link.group(1))
        title = html_to_text(link.group(2))
        snippet = html_to_text(_extract_first(r'<div[^>]*class="[^"]*\bb_caption\b[^"]*"[^>]*>.*?<p[^>]*>(.*?)</p>',
                                              block))
        if href.startswith("http") and title:
            out.append({"url": href, "title": title, "snippet": snippet})
        if len(out) >= limit:
            break
    return out


def _yahoo(query: str, limit: int):
    url = "https://search.yahoo.com/search?" + urllib.parse.urlencode({"p": query, "ei": "UTF-8"})
    html = _request(url, referer="https://search.yahoo.com/")
    blocks = re.findall(r'<div[^>]*class="[^"]*\bdd\b[^"]*\balgo\b[^"]*"[^>]*>(.*?)'
                        r'(?=<div[^>]*class="[^"]*\bdd\b[^"]*\balgo\b|</li><li|\Z)', html, re.I | re.S)
    out = []
    for block in blocks:
        link = re.search(r'<a[^>]*href="([^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>', block, re.I | re.S)
        if not link:
            continue
        href = _unwrap_yahoo_url(link.group(1))
        title = html_to_text(link.group(2))
        snippet = html_to_text(_extract_first(r'<div[^>]*class="[^"]*\bcompText\b[^"]*"[^>]*>.*?<p[^>]*>(.*?)</p>',
                                              block))
        if href.startswith("http") and title:
            out.append({"url": href, "title": title, "snippet": snippet})
        if len(out) >= limit:
            break
    return out


ENGINES = {"duckduckgo": _ddg, "ddg": _ddg, "bing": _bing, "yahoo": _yahoo}


_TRACKING = re.compile(r"^(utm_|ref_?$|fbclid$|gclid$|mc_|_hs|igshid$|spm$)")


def _normalize_url(u: str) -> str:
    """Canonicalize for dedupe: lowercase scheme/host, drop trailing slash, strip tracking params and
    the fragment. Best-effort — returns the input (slash-trimmed) on a parse error or a non-URL token."""
    try:
        p = urllib.parse.urlsplit(u)
    except ValueError:
        return u
    if not p.scheme and not p.netloc:                # not a real URL (e.g. a test token) — leave as-is
        return u.rstrip("/") or u
    path = p.path.rstrip("/") or "/"
    keep = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not _TRACKING.match(k.lower())]
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path,
                                    urllib.parse.urlencode(keep), ""))


def rrf(rankings, k: int = 60):
    """Reciprocal-rank fusion: merge ranked lists, dedupe by CANONICAL url, score Σ 1/(k + rank).
    Items keep their original url; only the dedup key is normalized (trailing-slash/tracking/case)."""
    scores, meta = {}, {}
    for results in rankings:
        for rank, item in enumerate(results):
            key = _normalize_url(item["url"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            meta.setdefault(key, item)
    return [meta[key] for key in sorted(scores, key=lambda x: scores[x], reverse=True)]


def search(query: str, *, limit: int = 8, engines=None) -> dict:
    names = list(engines) if engines else list(_DEFAULT_ENGINES)
    rankings, errors = [], {}
    for name in names:
        fn = ENGINES.get(name)
        if not fn:
            errors[name] = "unknown engine"
            continue
        try:
            res = fn(query, limit)
        except Exception as e:
            errors[name] = str(e)
            continue
        if res:
            rankings.append(res)
        else:
            errors[name] = "no results"
    if not rankings:
        return {"ok": False, "query": query, "errors": errors,
                "hint": "all engines empty/failed — fall back to native WebSearch."}
    fused = rrf(rankings)[:limit] if len(rankings) > 1 else rankings[0][:limit]
    return {"ok": True, "query": query, "count": len(fused), "results": fused,
            "engines": names, "errors": errors or None}
