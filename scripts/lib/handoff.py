"""Handoff continuity gate: the orchestrator runs this after every agent returns to confirm the agent
wrote a valid handoff (6 sections + a recognized Status). A missing/malformed handoff breaks resume —
the run's only memory — so it is caught immediately rather than discovered on resume.
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

HANDOFF_SECTIONS = ("Summary", "Changes", "Decisions", "Verification", "Issues", "Next")
VALID_HANDOFF_STATUSES = ("complete", "partial", "blocked")
HANDOFF_WARN_LINES = 120

# agent-guide §13 requires a CONCRETE Evidence checkpoint. A body that is empty or only a hollow
# phrase ("all good", "looks fine", "made changes") is not evidence — the orchestrator was supposed
# to reject these by hand (orchestrator-guide §3.2); this makes it mechanical. Kept deliberately
# conservative (whole-body match only) so a real checkpoint citing an artifact never false-trips.
_GENERIC_EVIDENCE = re.compile(
    r"^(all good|looks?\s+(?:fine|good|great|correct|ok)|made\s+(?:the\s+)?changes?|"
    r"followed\s+the\s+plan|no\s+issues?|done|completed?|ok|fine|good|n/?a|"
    r"lgtm|ship\s+it|wip|done\s+deal|good\s+to\s+go)[.!]*$",
    re.IGNORECASE,
)


def _evidence_checkpoint(text: str):
    """Return (present, generic) for the handoff's `Evidence checkpoint:` line (agent-guide §13)."""
    m = re.search(r"^[-*\s]*Evidence\s+checkpoint\s*:\s*(.*)$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return (False, False)
    body = m.group(1).strip()
    # drop an optional leading verdict word + separator so we judge the substance, not the label
    core = re.sub(r"^(confirmed|revised|invalidated)\b[\s:.–—-]*", "", body,
                  flags=re.IGNORECASE).strip()
    generic = (not core) or bool(_GENERIC_EVIDENCE.match(core))
    return (True, generic)


def _validate_handoff(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "path": str(p), "exists": False, "error": "handoff file does not exist"}
    text = p.read_text(encoding="utf-8", errors="replace")
    present = [s for s in HANDOFF_SECTIONS
              if re.search(rf"^##\s+{s}\b", text, re.MULTILINE | re.IGNORECASE)]
    missing = [s for s in HANDOFF_SECTIONS if s not in present]
    status = re.search(r"^[-*\s]*Status:\s*(\S+)", text, re.MULTILINE | re.IGNORECASE)
    status_val = status.group(1).lower().rstrip(".,") if status else None
    status_ok = status_val in VALID_HANDOFF_STATUSES
    ev_present, ev_generic = _evidence_checkpoint(text)
    ev_ok = ev_present and not ev_generic
    empty = not text.strip()
    line_count = len(text.splitlines())
    too_long = line_count > HANDOFF_WARN_LINES
    return {"ok": (not empty) and (not missing) and status_ok and ev_ok, "path": str(p),
            "exists": True, "empty": empty, "sections_present": present, "sections_missing": missing,
            "status": status.group(1) if status else None, "status_valid": status_ok,
            "evidence_checkpoint_present": ev_present, "evidence_checkpoint_generic": ev_generic,
            "evidence_checkpoint_ok": ev_ok, "line_count": line_count,
            "line_warn": too_long, "line_warn_threshold": HANDOFF_WARN_LINES}


def cmd_handoff_check(args) -> dict:
    if args.file:
        return _validate_handoff(args.file)
    if not args.workstream:
        return {"ok": False, "error": "give a handoff PATH, or --workstream SLUG [--agent NAME]"}
    d = Path(".devx/workstreams") / args.workstream / "handoffs"
    pattern = f"*-{args.agent}-*.md" if args.agent else "*.md"
    cands = sorted(d.glob(pattern), key=lambda p: p.stat().st_mtime) if d.exists() else []
    if args.newer_than:
        cands = [c for c in cands
                 if datetime.datetime.fromtimestamp(c.stat().st_mtime, datetime.timezone.utc)
                 .strftime("%Y-%m-%dT%H:%M:%SZ") > args.newer_than]
    if not cands:
        return {"ok": False, "exists": False, "workstream": args.workstream, "agent": args.agent,
                "error": "no matching handoff found — the agent did not write one"}
    res = _validate_handoff(cands[-1])
    res["matched"] = str(cands[-1])
    res["candidates"] = len(cands)
    return res
