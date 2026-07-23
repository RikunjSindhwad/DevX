"""Per-tier fetch primitives. urllib is the always-present stdlib floor; `requests` is used only if
installed (import-guarded). GitHub blob→raw and Wayback CDX are SWE-relevant fallbacks.

NOTE: all network calls go through `urllib.request.urlopen(...)` *module-qualified* (not a bound
`from urllib.request import urlopen`) so a test that patches `urllib.request.urlopen` still intercepts
them after this code moved out of the monolith.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

_UA = "Mozilla/5.0 (devx)"


def via_urllib(url: str) -> str:
    """Stdlib GET → decoded body. Raises on any network/HTTP error (caller records the attempt)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def via_requests(url: str) -> str:
    """Optional tier — only if `requests` is installed; otherwise raises ImportError and the cascade
    skips it. `requests` handles redirects/encinging more robustly than the urllib floor."""
    import requests  # optional
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=30)
    resp.raise_for_status()
    return resp.text


def github_blob_to_raw(url: str) -> str | None:
    """https://github.com/{owner}/{repo}/blob/{ref}/{path} → raw.githubusercontent.com equivalent.
    Pure string transform (no network) so it is unit-testable offline. Returns None if not a blob URL."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/blob/(.+)$", url)
    if not m:
        return None
    return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"


def via_github_raw(url: str) -> str:
    """Fetch a GitHub blob URL as raw source (skips the HTML wrapper). Raises if not a blob URL."""
    raw = github_blob_to_raw(url)
    if not raw:
        raise ValueError("not a github blob url")
    return via_urllib(raw)


def via_wayback(url: str) -> str:
    """Last-resort: fetch the closest Wayback Machine snapshot via the CDX availability API.
    Rescues pages that 404/moved or transiently block the live fetch."""
    cdx = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    req = urllib.request.Request(cdx, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    snap = (data.get("archived_snapshots") or {}).get("closest") or {}
    if not snap.get("available") or not snap.get("url"):
        raise RuntimeError("no wayback snapshot available")
    return via_urllib(snap["url"])
