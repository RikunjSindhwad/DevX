"""Shared helpers, constants, skip-marks, and utility symbols for all test modules."""
import datetime
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import devx_lib as dx

# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

def run(capsys, *argv):
    """Invoke the CLI exactly as a caller would; return (parsed_json, exit_code)."""
    code = dx.main(list(argv))
    return json.loads(capsys.readouterr().out), code


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

GOOD = ("# Topic Title\n\nBody text.\n\n"
        "> Source: https://ex.com/a · auto-promoted by researcher · 2026-06-20\n")

VALID_HANDOFF = ("# Handoff: implementer — T01\n- Status: complete\n"
                 "## Summary\ns\n## Changes\nc\n## Decisions\nd\n"
                 "## Verification\n- Evidence checkpoint: confirmed — pytest -q -> 4 passed; T01 met\n"
                 "## Issues\nnone\n## Next\nn\n")


# ---------------------------------------------------------------------------
# Skip marks
# ---------------------------------------------------------------------------

HAS_FTS5 = dx.fts5_available()
HAS_RG = shutil.which("rg") is not None

requires_fts5 = pytest.mark.skipif(not HAS_FTS5, reason="sqlite fts5 not available")
requires_rg = pytest.mark.skipif(not HAS_RG, reason="ripgrep not installed")


# ---------------------------------------------------------------------------
# validate_promotion helper
# ---------------------------------------------------------------------------

def _v(text, **kw):
    kw.setdefault("url_checker", lambda u: ("live", 200))
    kw.setdefault("today", datetime.date(2026, 6, 21))
    kw.setdefault("vault_titles", {})
    kw.setdefault("vault_slugs", set())
    return dx.validate_promotion(text, **kw)


def _git(*a):
    subprocess.run(["git", *a], capture_output=True)


# ---------------------------------------------------------------------------
# doctor helper
# ---------------------------------------------------------------------------

def _which_present(*present):
    return lambda name: ("/usr/bin/" + name) if name in present else None


# ---------------------------------------------------------------------------
# URL / HTTP stand-ins
# ---------------------------------------------------------------------------

class _Resp:
    """Minimal urlopen() context-manager stand-in."""
    def __init__(self, body="", status=200):
        self._b, self.status = body, status

    def read(self):
        return self._b.encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _engine_urlopen(ddg="", bing="", yahoo=""):
    def f(req, timeout=None):
        u = req.full_url
        return _Resp(ddg if "duckduckgo" in u else bing if "bing.com" in u else yahoo if "yahoo.com" in u else "")
    return f
