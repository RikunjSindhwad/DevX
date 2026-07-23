"""Tests for the state.md consistency gate (obs 23/25/30)."""
from helpers import run

_COMPLETE_DRIFT = (
    "# State\n**STATUS: COMPLETE.**\n\n## Phase completion status\n"
    "| Phase | Status | Notes |\n|---|---|---|\n"
    "| P01 — Scaffold | DONE (abc123) | |\n"
    "| P08 — GUI | PAUSED | operator checkpoint |\n"
    "| P09 — Packaging | NOT STARTED | blocked on P08 |\n"
)
_CLEAN = (
    "# State\n**STATUS: COMPLETE.**\n\n## Phase completion status\n"
    "| Phase | Status | Notes |\n|---|---|---|\n"
    "| P01 — Scaffold | DONE (abc123) | |\n"
    "| P02 — Core | DONE (def456) | |\n"
)


def _write(ws, slug, text):
    sd = ws / ".devx" / "workstreams" / slug / "state.md"
    sd.parent.mkdir(parents=True)
    sd.write_text(text)
    return sd


def _roadmap(ws, slug, text):
    rd = ws / ".devx" / "workstreams" / slug / "roadmap.md"
    rd.parent.mkdir(parents=True, exist_ok=True)
    rd.write_text(text)
    return rd


def _summary(ws, slug, phase_dir):
    sm = ws / ".devx" / "workstreams" / slug / "phases" / phase_dir / "summary.md"
    sm.parent.mkdir(parents=True, exist_ok=True)
    sm.write_text("# summary\n")
    return sm


def test_state_drift_detected(ws, capsys):
    _write(ws, "w", _COMPLETE_DRIFT)
    res, code = run(capsys, "state", "check", "--workstream", "w")
    assert code == 1 and res["ok"] is False
    assert res["issues"] and res["issues"][0]["type"] == "status_drift"
    assert len(res["incomplete_phases"]) == 2


def test_state_clean_passes(ws, capsys):
    _write(ws, "w2", _CLEAN)
    res, code = run(capsys, "state", "check", "--workstream", "w2")
    assert code == 0 and res["ok"] is True and res["incomplete_phases"] == []


def test_state_missing_file(ws, capsys):
    res, code = run(capsys, "state", "check", "--workstream", "ghost")
    assert code == 1 and res["exists"] is False


def test_state_in_progress_with_paused_is_not_drift(ws, capsys):
    # only COMPLETE+unfinished is drift; an in-progress workstream with a paused phase is fine
    _write(ws, "w3", "# State\nSTATUS: in-progress\n\n## Phase completion status\n"
                     "| Phase | Status |\n|---|---|\n| P08 — GUI | PAUSED |\n")
    res, code = run(capsys, "state", "check", "--workstream", "w3")
    assert code == 0 and res["ok"] is True


# --- JIT roadmap cross-checks (Context B1 / Harness F6 / Loop F-05) ---
_ROADMAP_UNFINISHED = (
    "# Roadmap\n\n| Phase | Status | Notes |\n|---|---|---|\n"
    "| P01 — Scaffold | done | shipped |\n"
    "| P02 — Core | in-progress | mid-flight |\n"
)
_ROADMAP_ALL_DONE = (
    "# Roadmap\n\n| Phase | Status | Notes |\n|---|---|---|\n"
    "| P01 — Scaffold | done | |\n"
    "| P02 — Core | done | |\n"
)


def test_state_roadmap_unfinished_with_complete_state_is_drift(ws, capsys):
    # state.md claims completion but a roadmap phase is still in-progress → roadmap_drift
    _write(ws, "r1", "# State\n**STATUS: COMPLETE.**\n")
    _roadmap(ws, "r1", _ROADMAP_UNFINISHED)
    _summary(ws, "r1", "01-scaffold")
    res, code = run(capsys, "state", "check", "--workstream", "r1")
    assert code == 1 and res["ok"] is False
    assert any(i["type"] == "roadmap_drift" for i in res["issues"])
    assert res["roadmap_unsettled"] and res["roadmap_unsettled"][0]["status"] == "in-progress"


def test_state_roadmap_all_done_with_summaries_is_clean(ws, capsys):
    # every done phase has a matching summary.md → no drift
    _write(ws, "r2", "# State\n**STATUS: COMPLETE.**\n")
    _roadmap(ws, "r2", _ROADMAP_ALL_DONE)
    _summary(ws, "r2", "01-scaffold")
    _summary(ws, "r2", "02-core")
    res, code = run(capsys, "state", "check", "--workstream", "r2")
    assert code == 0 and res["ok"] is True
    assert res["roadmap_done"] == 2 and res["phase_summaries"] == 2 and res["issues"] == []


def test_state_done_phase_missing_summary_is_drift(ws, capsys):
    # a roadmap phase marked done but no summary.md on disk → summary_drift
    _write(ws, "r3", "# State\nSTATUS: in-progress\n")
    _roadmap(ws, "r3", _ROADMAP_ALL_DONE)
    _summary(ws, "r3", "01-scaffold")          # only one of two done phases has a summary
    res, code = run(capsys, "state", "check", "--workstream", "r3")
    assert code == 1 and res["ok"] is False
    assert any(i["type"] == "summary_drift" for i in res["issues"])
    assert res["roadmap_done"] == 2 and res["phase_summaries"] == 1


def test_state_dispatch_audit_is_advisory(ws, capsys):
    _write(ws, "w4", _CLEAN)
    # two structured DISPATCH lines, zero handoffs → gap=2, but ok stays True (advisory only)
    (ws / ".devx" / "log.md").write_text(
        "[2026-06-23T10:00:00Z] DISPATCH orchestrator — "
        "workstream=w4 agent=implementer return_as=01-implementer-t01.md\n"
        "[2026-06-23T10:05:00Z] DISPATCH orchestrator — "
        "workstream=w4 agent=reviewer return_as=02-reviewer-p01.md\n")
    res, code = run(capsys, "state", "check", "--workstream", "w4")
    assert code == 0 and res["ok"] is True
    assert res["dispatch_audit"]["dispatches"] == 2 and res["dispatch_audit"]["gap"] == 2
    assert res["dispatch_audit"]["missing"] == [
        "01-implementer-t01.md",
        "02-reviewer-p01.md",
    ]


def test_state_dispatch_audit_is_scoped_and_matches_exact_returns(ws, capsys):
    _write(ws, "alpha", _CLEAN)
    hdir = ws / ".devx" / "workstreams" / "alpha" / "handoffs"
    hdir.mkdir(parents=True, exist_ok=True)
    (hdir / "01-researcher-api.md").write_text("# returned\n")
    # An unrelated handoff cannot conceal alpha's missing exact return. Legacy lines are ignored because
    # they cannot be attributed safely; beta's structured dispatch is scoped out.
    (hdir / "99-unrelated.md").write_text("# unrelated\n")
    (ws / ".devx" / "log.md").write_text(
        "[2026-07-23T10:00:00Z] DISPATCH orchestrator — "
        "workstream=alpha agent=researcher return_as=01-researcher-api.md\n"
        "[2026-07-23T10:01:00Z] DISPATCH orchestrator — "
        "workstream=alpha agent=researcher return_as=02-researcher-auth.md\n"
        "[2026-07-23T10:02:00Z] DISPATCH orchestrator — "
        "workstream=beta agent=reviewer return_as=01-reviewer-beta.md\n"
        "[2026-07-23T10:03:00Z] DISPATCH orchestrator — old unscoped entry\n"
    )

    res, code = run(capsys, "state", "check", "--workstream", "alpha")
    audit = res["dispatch_audit"]
    assert code == 0 and res["ok"] is True
    assert audit["dispatches"] == 2
    assert audit["present"] == ["01-researcher-api.md"]
    assert audit["missing"] == ["02-researcher-auth.md"]
    assert audit["gap"] == 1
    assert audit["handoffs_on_disk"] == 2
    assert audit["legacy_dispatches_ignored"] == 1


def test_state_dispatch_without_return_as_is_visible_but_advisory(ws, capsys):
    _write(ws, "w5", _CLEAN)
    (ws / ".devx" / "log.md").write_text(
        "[2026-07-23T11:00:00Z] DISPATCH orchestrator — "
        "workstream=w5 agent=designer task=plan\n"
    )

    res, code = run(capsys, "state", "check", "--workstream", "w5")
    assert code == 0 and res["ok"] is True
    assert res["dispatch_audit"]["without_return_as"] == 1
    assert res["dispatch_audit"]["gap"] == 1


def test_state_dispatch_reused_return_as_is_visible(ws, capsys):
    _write(ws, "w6", _CLEAN)
    hdir = ws / ".devx" / "workstreams" / "w6" / "handoffs"
    hdir.mkdir(parents=True, exist_ok=True)
    (hdir / "01-researcher-api.md").write_text("# returned once\n")
    line = (
        "[2026-07-23T12:00:00Z] DISPATCH orchestrator — "
        "workstream=w6 agent=researcher return_as=01-researcher-api.md\n"
    )
    (ws / ".devx" / "log.md").write_text(line + line)

    res, code = run(capsys, "state", "check", "--workstream", "w6")
    assert code == 0 and res["ok"] is True
    assert res["dispatch_audit"]["duplicate_return_as"] == ["01-researcher-api.md"]
    assert res["dispatch_audit"]["gap"] == 1
