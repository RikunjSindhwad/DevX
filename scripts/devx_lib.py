#!/usr/bin/env python3
"""devx_lib — the CLI ROUTER for the DevX plugin's non-native tool surface.

No business logic lives here: this file only wires `sys.path`, imports the implementation from the
co-located `lib/` package, re-exports the names callers/tests reference, and dispatches subcommands via
argparse. Each subsystem is its own module:

    lib/config.py     vault/DB path resolution + the path-containment guard
    lib/probes.py     shared capability probes (fts5_available)
    lib/retrieval.py  markdown chunker + FTS5 index + kb_search cascade (index, kb_search)
    lib/fetch/        tiered fetch + extraction cascade + multi-engine search (fetch, search)
    lib/github.py     GitHub code/repo search via gh (github_search)
    lib/validate.py   auto-promote validation gate (validate)
    lib/handoff.py    handoff continuity gate (handoff_check)
    lib/state_check.py state.md consistency gate (state check)
    lib/vault.py      vault maintenance: layout stats + split-signal (vault)
    lib/doctor.py     environment preflight (doctor)

`log` is deliberately NOT here: it is a dependency-free bash helper in bin/devx so lifecycle logging
works even when Python/venv is broken. JSON on stdout is a RESULT, not an input contract.
"""
from __future__ import annotations

import argparse
import json
import shutil          # noqa: F401  imported so tests can patch `dx.shutil.which` (shared module)
import subprocess      # noqa: F401  imported so tests can patch `dx.subprocess.run` (shared module)
import sys
import urllib.error    # noqa: F401
import urllib.request  # noqa: F401  imported so tests can patch `dx.urllib.request.urlopen`
from pathlib import Path

# Make the co-located lib/ package importable however devx_lib is invoked (CLI, bin/devx, or pytest).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:   # pragma: no cover - bootstrap; already on path under pytest
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Module handles (so tests can patch e.g. dx.probes.fts5_available, dx.validate._check_url_live).
from lib import doctor, probes, retrieval, validate                            # noqa: E402,F401
# Re-exports — the public + test-referenced surface resolves on `devx_lib` for back-compat.
from lib.config import DB_NAME, _within, db_path, vault_dir                     # noqa: E402,F401
from lib.probes import fts5_available                                           # noqa: E402,F401
from lib.retrieval import (GRAPH_MAX_NEIGHBORS, GRAPH_TOP_HITS,                 # noqa: E402,F401
                           MIN_LOCAL_RESULTS, PROJECT_DB, PROJECT_TOP,
                           SNIPPET_TOKENS, _build_index, _chunk_markdown,
                           _doc_meta, _extract_links, _fm_field, _frontmatter,
                           _fts_search, _graph_neighbors, _project_items,
                           _rg_search, _sanitize, _vault_items,
                           cmd_index, cmd_kb_search, doc_body, meta_slugs,
                           meta_titles, norm_title)
from lib.fetch import fetch_url, search as web_search                           # noqa: E402,F401
from lib.fetch.tiers import _cache_fresh, _ttl_for                              # noqa: E402,F401
from lib.fetch.extract import html_to_text as _html_to_text                     # noqa: E402,F401
from lib.github import cmd_github_search                                        # noqa: E402,F401
from lib.validate import (PROMOTE_MAX_AGE_DAYS, _check_url_live, _extract_urls,  # noqa: E402,F401
                          _parse_iso_date, _vault_slugs, _vault_titles,
                          cmd_validate, validate_promotion)
from lib.handoff import _validate_handoff, cmd_handoff_check                     # noqa: E402,F401
from lib.state_check import check_state, cmd_state                              # noqa: E402,F401
from lib.vault import cmd_vault                                                # noqa: E402,F401
from lib.doctor import cmd_doctor                                              # noqa: E402,F401


# ----------------------------------------------------- fetch & search (thin adapters)
# The implementation lives in lib/fetch/; these just map argparse Namespaces to the library calls.
def cmd_fetch(args) -> dict:
    return fetch_url(args.url, refresh=args.refresh, max_chars=args.max_chars)


def cmd_search(args) -> dict:
    engines = [e.strip() for e in args.engines.split(",")] if getattr(args, "engines", None) else None
    return web_search(args.query, limit=args.limit, engines=engines)


# ------------------------------------------------------------------------- main
def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="devx", description="DevX retrieval library")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("index", help="build/refresh an FTS5 index (vault | project | all)")
    sp.add_argument("--scope", choices=["vault", "project", "all"], default="vault")
    sp.set_defaults(fn=cmd_index)

    sp = sub.add_parser("kb_search", help="search vault and/or project knowledge")
    sp.add_argument("query")
    sp.add_argument("--scope", choices=["vault", "project", "all"], default="vault")
    sp.add_argument("--limit", type=int, default=8)
    sp.set_defaults(fn=cmd_kb_search)

    sp = sub.add_parser("fetch", help="cached, text-extracted URL fetch")
    sp.add_argument("url")
    sp.add_argument("--refresh", action="store_true")
    sp.add_argument("--max-chars", type=int, default=6000)
    sp.set_defaults(fn=cmd_fetch)

    sp = sub.add_parser("search", help="web search -> candidate URLs (multi-engine, RRF-fused)")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=8)
    sp.add_argument("--engines", help="comma-separated (duckduckgo,bing,yahoo or ddg,bing,yahoo); default all three")
    sp.set_defaults(fn=cmd_search)

    sp = sub.add_parser("github_search", help="GitHub code/repo search via gh")
    sp.add_argument("query")
    sp.add_argument("--kind", choices=["code", "repos"], default="code")
    sp.add_argument("--limit", type=int, default=8)
    sp.set_defaults(fn=cmd_github_search)

    sp = sub.add_parser("validate", help="validate a candidate vault doc before promotion "
                                         "(stale links, provenance, dedup, generalization)")
    sp.add_argument("file", help="path to the candidate markdown")
    sp.add_argument("--promote-to", help="vault-relative path; on PASS, write into the vault and reindex")
    sp.add_argument("--update", action="store_true", help="with --promote-to: overwrite a duplicate entry")
    sp.add_argument("--offline", action="store_true", help="skip network link checks (URLs -> unverified)")
    sp.add_argument("--max-age-days", type=int, default=PROMOTE_MAX_AGE_DAYS)
    sp.set_defaults(fn=cmd_validate)

    sp = sub.add_parser("handoff_check", help="verify an agent wrote a valid handoff "
                                              "(6 sections + Status); exits non-zero if not")
    sp.add_argument("file", nargs="?", help="explicit handoff path (or use --workstream)")
    sp.add_argument("--workstream", help="find the newest handoff under this workstream")
    sp.add_argument("--agent", help="with --workstream: match *-{agent}-*.md")
    sp.add_argument("--newer-than", help="ISO-8601 UTC; only consider handoffs modified after this")
    sp.set_defaults(fn=cmd_handoff_check)

    sp = sub.add_parser("state", help="state.md consistency gate "
                                      "(flags STATUS:COMPLETE while phases are unfinished); exits non-zero")
    ssub = sp.add_subparsers(dest="state_action")
    sc = ssub.add_parser("check", help="check a workstream's state.md for status drift")
    sc.add_argument("file", nargs="?", help="explicit state.md path (or use --workstream)")
    sc.add_argument("--workstream", help="check .devx/workstreams/{slug}/state.md")
    sp.set_defaults(fn=cmd_state)

    sp = sub.add_parser("vault", help="vault maintenance: stats (per-category distribution + split signal)")
    vsub = sp.add_subparsers(dest="vault_action")
    vstats = vsub.add_parser("stats", help="per-category file distribution + a 'time to split' signal")
    vstats.add_argument("--split-threshold", type=int, default=None,
                        help="flag a folder holding more than N files directly (default 20)")
    sp.set_defaults(fn=cmd_vault)

    sp = sub.add_parser("doctor", help="environment preflight for /devx:devx-init (tools + FTS5); "
                                       "exits non-zero if a required tool is missing")
    sp.set_defaults(fn=cmd_doctor)

    args = p.parse_args(argv)
    result = args.fn(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # validate/handoff_check/doctor/state are GATES: their exit code is the contract callers branch on.
    if args.cmd in ("validate", "handoff_check", "doctor", "state") and not result.get("ok", True):
        return 1
    return 0


if __name__ == "__main__":   # pragma: no cover - process entrypoint, not exercised in-process
    sys.exit(main())
