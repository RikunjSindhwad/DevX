"""DevX fetch/search subsystem (SWE-domain, stdlib-floor).

Modular by design — `devx_lib.py` keeps only thin CLI adapters; the logic lives here:
  - extract      — HTML → text/markdown, cascade (trafilatura → BeautifulSoup → stdlib strip).
  - http_client  — per-tier primitives: urllib (floor), GitHub-raw conversion, Wayback CDX.
  - tiers        — fetch orchestration: cache → github_raw → urllib → wayback → extract → cache.
  - web_search   — DuckDuckGo/Bing/Yahoo search with reciprocal-rank-fusion dedupe.

Everything degrades gracefully: optional deps (requests, trafilatura, bs4) are import-guarded, so
absent them DevX still fetches via stdlib `urllib` and extracts via the regex strip. Pentest-style
anti-bot browser tiers (Scrapling/Camoufox) are deliberately NOT included — wrong domain, heavy deps.
"""
from .tiers import fetch_url           # noqa: F401
from .web_search import search         # noqa: F401
from .extract import html_to_text, extract_markdown  # noqa: F401

__all__ = ["fetch_url", "search", "html_to_text", "extract_markdown"]
