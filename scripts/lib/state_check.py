"""State-consistency gate for a workstream's state.md (the resume spine).

A state.md that declares the workstream COMPLETE while its phase table still lists PAUSED /
NOT-STARTED / BLOCKED phases is a self-contradiction (observed in a dogfood run) that corrupts
resume — the run's only memory. `devx state check` catches that deterministically and exits
non-zero (a GATE, like handoff_check).

The JIT model rarely writes a `| Pnn | STATUS |` table into state.md, so that check alone passed
vacuously. When `--workstream {slug}` is given we ALSO read the workstream's roadmap.md and cross-
check it against state.md and the phases/ dir on disk:
  (a) state.md claims completion (STATUS:COMPLETE or "ready to ship"/"complete" prose) while any
      roadmap phase Status is not in {done, dropped} → drift; and
  (b) a roadmap phase marked `done` whose phases/{NN}-*/summary.md is missing on disk → drift
      (compared as done-row count vs summary.md count; a shortfall is drift).
The legacy state.md-table check is kept as an additional signal.

It also reports an ADVISORY audit of this workstream's structured DISPATCH log lines against their
exact `return_as` handoffs. Missing handoffs can therefore no longer be hidden by dispatches or files
from another workstream. The audit is advisory only (an operator-cancelled dispatch is a legitimate
gap), so it never flips `ok`.
"""
from __future__ import annotations

import re
from pathlib import Path

_COMPLETE = re.compile(r"STATUS:\s*COMPLETE", re.IGNORECASE)
_COMPLETE_PROSE = re.compile(r"\b(ready\s+to\s+ship|complete)\b", re.IGNORECASE)
_INCOMPLETE = re.compile(r"\b(PAUSED|NOT\s*STARTED|BLOCKED|IN\s*PROGRESS|TODO)\b", re.IGNORECASE)
# roadmap phase Status vocabulary (agent-guide / roadmap.md): a phase is "settled" if done|dropped.
_ROADMAP_STATUSES = ("next", "in-progress", "done", "re-scoped", "dropped")
_SETTLED = {"done", "dropped"}
_DISPATCH = re.compile(r"^\[.*?\]\s+DISPATCH\b")
_DISPATCH_WORKSTREAM = re.compile(r"\bworkstream=([A-Za-z0-9._-]+)\b")
_DISPATCH_RETURN_AS = re.compile(r"\breturn_as=([A-Za-z0-9._-]+\.md)\b")


def _phase_statuses(text: str):
    """(phase, status) pairs from the markdown phase-status table rows (| Pnn … | STATUS | …)."""
    rows = []
    for ln in text.splitlines():
        if ln.count("|") < 2:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 2 and re.match(r"P\d", cells[0], re.IGNORECASE):
            rows.append((cells[0], cells[1]))
    return rows


def _roadmap_statuses(text: str):
    """(phase, status) pairs from roadmap.md rows; status normalized to a known roadmap word.

    Scans every table row's cells for one of the roadmap Status words (next|in-progress|done|
    re-scoped|dropped). The phase label is the first cell that looks like a phase id (Pnn / 01 …);
    if none, the whole row's first cell is used. Rows with no recognized status word are skipped.
    """
    rows = []
    for ln in text.splitlines():
        if ln.count("|") < 2:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        status = None
        for c in cells:
            low = c.lower()
            for s in _ROADMAP_STATUSES:
                # whole-cell match (allow trailing punctuation/notes via a word boundary)
                if re.fullmatch(rf"{re.escape(s)}\b.*", low):
                    status = s
                    break
            if status:
                break
        if not status:
            continue
        phase = next((c for c in cells if re.match(r"(P\d|\d{1,2}\b)", c, re.IGNORECASE)),
                     cells[0] if cells else "?")
        rows.append((phase, status))
    return rows


def _done_summaries(ws_dir: Path):
    """(done_phase_count, summary_file_count) for a workstream dir holding roadmap.md + phases/."""
    roadmap = ws_dir / "roadmap.md"
    if not roadmap.exists():
        return None
    rows = _roadmap_statuses(roadmap.read_text(encoding="utf-8", errors="replace"))
    done = sum(1 for _, st in rows if st == "done")
    summaries = len(list((ws_dir / "phases").glob("*/summary.md"))) if (ws_dir / "phases").exists() else 0
    return rows, done, summaries


def _dispatch_audit(devx_dir: Path, slug: str):
    log = devx_dir / "log.md"
    if not log.exists():
        return None

    dispatches = 0
    legacy_ignored = 0
    expected = []
    without_return_as = 0
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not _DISPATCH.search(line):
            continue
        workstream = _DISPATCH_WORKSTREAM.search(line)
        if not workstream:
            legacy_ignored += 1
            continue
        if workstream.group(1) != slug:
            continue
        dispatches += 1
        return_as = _DISPATCH_RETURN_AS.search(line)
        if return_as:
            expected.append(return_as.group(1))
        else:
            without_return_as += 1

    hdir = devx_dir / "workstreams" / slug / "handoffs"
    handoff_names = {p.name for p in hdir.glob("*.md")} if hdir.exists() else set()
    duplicates = sorted({name for name in expected if expected.count(name) > 1})
    missing = [name for name in expected if name not in handoff_names]
    present = [name for name in expected if name in handoff_names]
    return {
        "dispatches": dispatches,
        "expected_handoffs": len(expected),
        "present": present,
        "missing": missing,
        "duplicate_return_as": duplicates,
        "without_return_as": without_return_as,
        "legacy_dispatches_ignored": legacy_ignored,
        "handoffs_on_disk": len(handoff_names),
        "gap": len(missing) + without_return_as + len(duplicates),
        "note": "advisory: gap counts this workstream's structured DISPATCH entries whose exact "
                "return_as handoff is missing, was not logged, or was reused; cancelled dispatches are "
                "legitimate when explained by a NOTE",
    }


def check_state(state_path, ws_dir=None) -> dict:
    p = Path(state_path)
    if not p.exists():
        return {"ok": False, "exists": False, "path": str(p), "error": "state.md not found"}
    text = p.read_text(encoding="utf-8", errors="replace")
    complete = bool(_COMPLETE.search(text))
    claims_complete = complete or bool(_COMPLETE_PROSE.search(text))
    statuses = _phase_statuses(text)
    incomplete = [{"phase": ph, "status": st} for ph, st in statuses if _INCOMPLETE.search(st)]
    issues = []
    # legacy state.md-table signal (kept as an additional check)
    if complete and incomplete:
        issues.append({"type": "status_drift",
                       "detail": "STATUS:COMPLETE but the phase table lists unfinished phases: "
                                 + ", ".join(f"{i['phase']}={i['status']}" for i in incomplete)})

    res = {"ok": None, "exists": True, "path": str(p), "status_complete": complete,
           "phases": len(statuses), "incomplete_phases": incomplete}

    # JIT roadmap cross-checks: read roadmap.md + phases/ from the workstream dir, if available.
    if ws_dir is not None:
        ds = _done_summaries(Path(ws_dir))
        if ds is not None:
            rows, done, summaries = ds
            unsettled = [{"phase": ph, "status": st} for ph, st in rows if st not in _SETTLED]
            res["roadmap_phases"] = len(rows)
            res["roadmap_done"] = done
            res["phase_summaries"] = summaries
            res["roadmap_unsettled"] = unsettled
            # (a) state.md claims completion while a roadmap phase is not done/dropped
            if claims_complete and unsettled:
                issues.append({"type": "roadmap_drift",
                               "detail": "state.md claims completion but roadmap phases are "
                                         "unsettled: " + ", ".join(f"{u['phase']}={u['status']}"
                                                                    for u in unsettled)})
            # (b) more roadmap phases marked done than summary.md files on disk
            if done > summaries:
                issues.append({"type": "summary_drift",
                               "detail": f"{done} roadmap phase(s) marked done but only "
                                         f"{summaries} phases/*/summary.md on disk"})

    res["issues"] = issues
    res["ok"] = not issues
    return res


def cmd_state(args) -> dict:
    if getattr(args, "workstream", None):
        devx = Path(".devx")
        ws_dir = devx / "workstreams" / args.workstream
        res = check_state(ws_dir / "state.md", ws_dir=ws_dir)
        audit = _dispatch_audit(devx, args.workstream)
        if audit is not None:
            res["dispatch_audit"] = audit            # advisory — does NOT affect ok
        return res
    if getattr(args, "file", None):
        return check_state(args.file)
    return {"ok": False, "error": "give a state.md PATH, or --workstream SLUG"}
