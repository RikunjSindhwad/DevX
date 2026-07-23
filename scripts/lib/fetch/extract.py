"""HTML → text/markdown extraction.

`html_to_text` is the dependency-free stdlib floor (ported verbatim from the v1 inline helper, so its
behavior — and the search title parsing that relies on it — is unchanged). `extract_markdown` is a
cascade that prefers a richer extractor when one is installed, then degrades to the floor. Optional
imports never raise: a missing dep just means we fall back a tier.
"""
from __future__ import annotations

import html as html_lib
import re


def html_to_text(html: str) -> str:
    """Stdlib floor: drop <script>/<style>, strip tags, unescape a few entities, collapse blanks."""
    html = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = html_lib.unescape(text).replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def extract_markdown(html: str, url: str = "") -> tuple[str, str]:
    """Best-available extraction → (text, method). Tries trafilatura, then BeautifulSoup, then the
    stdlib strip. Returns the method used so callers/agents can see how a page was extracted."""
    try:
        import trafilatura  # optional, heavy-but-good
        out = trafilatura.extract(html, url=url or None, output_format="markdown",
                                  include_links=True, include_tables=True)
        if out and out.strip():
            return out.strip(), "trafilatura"
    except Exception:
        pass
    try:
        from bs4 import BeautifulSoup  # optional
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "noscript", "template"]):
            t.decompose()
        txt = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
        if txt:
            return txt, "beautifulsoup"
    except Exception:
        pass
    return html_to_text(html), "strip"
