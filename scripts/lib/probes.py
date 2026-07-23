"""Shared capability probes. Centralized here (not in the router) because they are called from several
modules (retrieval, validate, doctor); callers reference them MODULE-QUALIFIED
(`probes.fts5_available()`) so a single test patch on this module reaches every caller.
"""
from __future__ import annotations

import sqlite3


def fts5_available() -> bool:
    """Probe the live SQLite build rather than assuming FTS5 is compiled in."""
    try:
        c = sqlite3.connect(":memory:")
        c.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
        c.close()
        return True
    except sqlite3.OperationalError:
        return False
