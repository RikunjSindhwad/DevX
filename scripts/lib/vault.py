"""Vault maintenance surface. Today: `stats` — the per-category file distribution and a 'time to split'
signal for the emergent-sub-folder layout (flat categories at the top; a category sub-divides into
one-level sub-folders only once it grows). Retrieval never depends on the tree shape (kb_search hits the
FTS index + tags + links, and the indexer globs `**/*.md`), so this is a curation aid, not a perf path.
Stdlib-only; reads the file tree (the source of truth for layout), enriched best-effort with index counts.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from lib import probes
from lib.config import DB_NAME, db_path, vault_dir

SPLIT_THRESHOLD = 20      # >N .md files sitting DIRECTLY in one folder → suggest sub-foldering


def _count(d: Path, pattern: str) -> int:
    return sum(1 for _ in d.glob(pattern))


def _vault_stats(threshold: int) -> dict:
    """Walk the vault tree: per top-level category, total + directly-held .md counts and the sub-folder
    breakdown, flagging any folder whose DIRECT file count exceeds `threshold` as a split candidate."""
    root = vault_dir()
    if not root.exists():
        return {"ok": False, "error": f"vault not found: {root}"}
    categories, suggestions, total_files = [], [], 0
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        direct = _count(d, "*.md")
        total = _count(d, "**/*.md")
        subs = []
        for sd in sorted(p for p in d.iterdir() if p.is_dir()):
            sdirect = _count(sd, "*.md")
            subs.append({"name": sd.name, "files": _count(sd, "**/*.md"), "direct": sdirect})
            if sdirect > threshold:
                suggestions.append(f"{d.name}/{sd.name}/ holds {sdirect} files directly — sub-divide it")
        if direct > threshold:
            suggestions.append(
                f"{d.name}/ holds {direct} files directly — split into sub-folders by sub-topic "
                f"(e.g. {d.name}/<area>/)")
        categories.append({"category": d.name, "files": total, "direct": direct,
                           "subfolders": subs, "oversized": direct > threshold})
        total_files += total

    out = {"ok": True, "vault": str(root), "split_threshold": threshold,
           "total_files": total_files, "categories": categories, "split_suggestions": suggestions}

    # Best-effort index enrichment (stats must work with no index too — disk is the source of truth).
    db = db_path()
    if db.exists() and probes.fts5_available():
        try:
            conn = sqlite3.connect(str(db))
            try:
                out["indexed"] = {
                    "files": conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],
                    "chunks": conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
                    "links": conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]}
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    return out


def cmd_vault(args) -> dict:
    action = getattr(args, "vault_action", None)
    if action == "stats":
        return _vault_stats(getattr(args, "split_threshold", None) or SPLIT_THRESHOLD)
    return {"ok": False, "error": "usage: devx vault stats [--split-threshold N]"}
