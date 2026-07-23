"""Fetch orchestration: cache → tier cascade → extract → cache.

Entries under ``.devx/cache/fetch/<sha256(url)[:16]>.md`` use content-class TTLs and may also be
explicitly refreshed. Results retain the core ``ok, url, cached, path, chars, text`` keys and include
``tier``, ``extract``, and an ``attempts`` trail so an agent can cite why a fetch is weak.
Optional/heavy anti-bot tiers are intentionally absent.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from pathlib import Path

from . import http_client as hc
from .extract import extract_markdown

CACHE_DIR = ".devx/cache/fetch"

_DAY = 86400
# Per-content-class cache TTLs (seconds). A cached page older than its class TTL is treated as a
# MISS and re-fetched, so volatile pages don't go stale while stable specs aren't re-fetched needlessly.
# Tunable: edit the dict (each entry is (substr-regex, ttl_seconds), first match wins) or DEFAULT_TTL.
DEFAULT_TTL = 14 * _DAY
# NOTE: matched against url.lower(), so all patterns are lowercase.
_TTL_RULES = (
    (r"changelog|releases?|whats-?new|news|/blog/|/feed|atom\.xml|rss", 1 * _DAY),   # volatile → ~1 day
    (r"/rfc|datatracker\.ietf|/spec(s)?(/|\b)|/standard|w3\.org/tr|whatwg", 90 * _DAY),  # stable → ~90 days
)


def _ttl_for(url: str) -> int:
    """Cache TTL (seconds) for a URL by content class: changelog/releases/news → short (~1d);
    rfc/spec/standard → long (~90d); everything else → DEFAULT_TTL (~14d). First matching rule wins."""
    u = url.lower()
    for pat, ttl in _TTL_RULES:
        if re.search(pat, u):
            return ttl
    return DEFAULT_TTL


def _cache_fresh(cf: Path, url: str) -> bool:
    """True iff the cache file exists AND its age (now - mtime) is within the URL's TTL. A read-time
    miss (stale) falls through to a normal re-fetch, which overwrites the file (refreshing its mtime)."""
    try:
        age = time.time() - cf.stat().st_mtime
    except OSError:
        return False
    return age <= _ttl_for(url)


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file in the same dir + os.replace, so an interrupted write never leaves a
    partial file that a later fetch would trust as a cache hit."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _tier_order(url: str):
    """(name, fn) cascade. GitHub blob → raw first; `requests` only if installed; Wayback last."""
    order = []
    if hc.github_blob_to_raw(url):
        order.append(("github_raw", hc.via_github_raw))
    order.append(("urllib", hc.via_urllib))
    order.append(("requests", hc.via_requests))   # via_requests raises ImportError if absent → skipped
    order.append(("wayback", hc.via_wayback))
    return order


def fetch_url(url: str, *, refresh: bool = False, max_chars: int = 6000,
              cache_dir: str = CACHE_DIR) -> dict:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    cf = cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".md")
    # Cache hit ONLY when not forcing a refresh AND the entry is still fresh for its content class
    # A stale entry falls through and re-fetches, overwriting the file (resetting its mtime).
    if not refresh and _cache_fresh(cf, url):
        body = cf.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "url": url, "cached": True, "path": str(cf),
                "chars": len(body), "text": body[:max_chars], "tier": "cache",
                "ttl": _ttl_for(url)}

    raw, used, attempts = None, None, []
    for name, fn in _tier_order(url):
        try:
            body = fn(url)
        except ImportError:
            attempts.append({"tier": name, "ok": False, "note": "optional dep not installed"})
            continue
        except Exception as e:
            attempts.append({"tier": name, "ok": False, "error": str(e)})
            continue
        if body and body.strip():
            raw, used = body, name
            attempts.append({"tier": name, "ok": True})
            break
        attempts.append({"tier": name, "ok": False, "note": "empty body"})

    if raw is None:
        last_err = next((a.get("error") for a in reversed(attempts) if a.get("error")), "all tiers failed")
        return {"ok": False, "url": url, "error": last_err, "attempts": attempts,
                "hint": "tiers tried: " + ", ".join(a["tier"] for a in attempts) +
                        " — install optional deps (requests) for more reach, or verify the URL."}

    text, method = extract_markdown(raw, url)
    _atomic_write(cf, text)
    return {"ok": True, "url": url, "cached": False, "path": str(cf), "chars": len(text),
            "text": text[:max_chars], "tier": used, "extract": method, "attempts": attempts}
