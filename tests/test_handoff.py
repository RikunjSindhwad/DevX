"""Tests for handoff_check."""
import datetime
import os

from helpers import dx, run, VALID_HANDOFF


def test_handoff_valid(ws, capsys):
    p = ws / ".devx" / "h.md"; p.write_text(VALID_HANDOFF)
    res, code = run(capsys, "handoff_check", str(p))
    assert code == 0 and res["ok"] and res["status"] == "complete" and res["sections_missing"] == []
    assert res["line_warn"] is False and res["line_warn_threshold"] == 120


def test_handoff_missing_file(ws, capsys):
    res, code = run(capsys, "handoff_check", str(ws / "nope.md"))
    assert code == 1 and res["exists"] is False


def test_handoff_missing_sections(ws, capsys):
    p = ws / ".devx" / "h.md"; p.write_text("# H\n- Status: partial\n## Summary\ns\n")
    res, code = run(capsys, "handoff_check", str(p))
    assert code == 1 and "Next" in res["sections_missing"]


def test_handoff_by_workstream_picks_newest(ws, capsys):
    d = ws / ".devx" / "workstreams" / "w" / "handoffs"; d.mkdir(parents=True)
    (d / "01-implementer-t01.md").write_text(VALID_HANDOFF); os.utime(d / "01-implementer-t01.md", (1000, 1000))
    (d / "02-implementer-t02.md").write_text(VALID_HANDOFF); os.utime(d / "02-implementer-t02.md", (2000, 2000))
    res, code = run(capsys, "handoff_check", "--workstream", "w", "--agent", "implementer")
    assert code == 0 and res["matched"].endswith("02-implementer-t02.md") and res["candidates"] == 2


def test_handoff_workstream_none_found(ws, capsys):
    res, code = run(capsys, "handoff_check", "--workstream", "ghost")
    assert code == 1 and res["exists"] is False


# --- H-04: handoff_check requires a VALID Status: ---
def test_handoff_status_required_and_validated(ws, capsys):
    body = ("## Summary\ns\n## Changes\nc\n## Decisions\nd\n"
            "## Verification\n- Evidence checkpoint: confirmed — pytest -q -> 4 passed\n"
            "## Issues\nnone\n## Next\nn\n")
    (ws / "a.md").write_text("# H\n" + body)                       # no Status
    r, code = run(capsys, "handoff_check", str(ws / "a.md"))
    assert code == 1 and r["ok"] is False and r["status_valid"] is False
    (ws / "b.md").write_text("# H\n- Status: bogus\n" + body)       # invalid Status
    r, code = run(capsys, "handoff_check", str(ws / "b.md"))
    assert code == 1 and r["ok"] is False
    (ws / "c.md").write_text("# H\n- Status: complete\n" + body)    # valid
    r, code = run(capsys, "handoff_check", str(ws / "c.md"))
    assert code == 0 and r["ok"] is True and r["status_valid"] is True


def test_handoff_empty_file(ws, capsys):
    h = ws / ".devx" / "h.md"
    h.write_text("")
    res, _ = run(capsys, "handoff_check", str(h))
    assert res["ok"] is False and res["empty"] is True


def test_handoff_status_trailing_punctuation(ws, capsys):
    h = ws / ".devx" / "h2.md"
    h.write_text("- Status: complete.\n## Summary\ns\n## Changes\nc\n## Decisions\nd\n"
                 "## Verification\n- Evidence checkpoint: confirmed — ran pytest, 4 passed\n"
                 "## Issues\nnone\n## Next\nn\n")
    res, _ = run(capsys, "handoff_check", str(h))
    assert res["ok"] is True                                      # 'complete.' → rstrip → complete


def test_handoff_check_requires_path_or_workstream(ws, capsys):
    res, _ = run(capsys, "handoff_check")                         # neither PATH nor --workstream
    assert res["ok"] is False and "give a handoff PATH" in res["error"]


def test_handoff_check_newer_than_rejects_stale(ws, capsys):
    import time
    hd = ws / ".devx" / "workstreams" / "ws1" / "handoffs"
    hd.mkdir(parents=True)
    old = hd / "01-impl-t1.md"
    old.write_text(VALID_HANDOFF)
    past = time.time() - 3600
    os.utime(old, (past, past))                                  # handoff written an hour "ago"
    future = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res, _ = run(capsys, "handoff_check", "--workstream", "ws1", "--agent", "impl", "--newer-than", future)
    assert res["ok"] is False and res["exists"] is False          # stale handoff filtered → "did not write one"


def test_handoff_check_newer_than_accepts_fresh(ws, capsys):
    hd = ws / ".devx" / "workstreams" / "ws2" / "handoffs"
    hd.mkdir(parents=True)
    (hd / "02-impl-t2.md").write_text(VALID_HANDOFF)
    res, _ = run(capsys, "handoff_check", "--workstream", "ws2", "--agent", "impl",
                 "--newer-than", "2000-01-01T00:00:00Z")
    assert res["ok"] is True and res["matched"].endswith("02-impl-t2.md")   # fresh handoff accepted


# --- Evidence checkpoint enforcement (agent-guide §13; obs 14/15) ---
_NO_EC = ("# H\n- Status: complete\n## Summary\ns\n## Changes\nc\n## Decisions\nd\n"
          "## Verification\n{verif}\n## Issues\nnone\n## Next\nn\n")


def test_handoff_evidence_checkpoint_missing_rejected(ws, capsys):
    (ws / "e.md").write_text(_NO_EC.format(verif="ran the tests, all passed"))
    res, code = run(capsys, "handoff_check", str(ws / "e.md"))
    assert code == 1 and res["ok"] is False
    assert res["evidence_checkpoint_present"] is False and res["evidence_checkpoint_ok"] is False


def test_handoff_evidence_checkpoint_generic_rejected(ws, capsys):
    (ws / "g.md").write_text(_NO_EC.format(verif="- Evidence checkpoint: all good"))
    res, code = run(capsys, "handoff_check", str(ws / "g.md"))
    assert code == 1 and res["ok"] is False and res["evidence_checkpoint_generic"] is True


def test_handoff_evidence_checkpoint_verdict_then_hollow_rejected(ws, capsys):
    (ws / "g2.md").write_text(_NO_EC.format(verif="- Evidence checkpoint: confirmed — looks fine"))
    res, code = run(capsys, "handoff_check", str(ws / "g2.md"))
    assert code == 1 and res["evidence_checkpoint_generic"] is True


def test_handoff_evidence_checkpoint_hollow_phrases_rejected(ws, capsys):
    # F9: extended hollow forms ("looks great!", "lgtm", "ship it", etc.) must be rejected,
    # while a concrete checkpoint still passes.
    (ws / "h1.md").write_text(_NO_EC.format(verif="- Evidence checkpoint: looks great!"))
    res, code = run(capsys, "handoff_check", str(ws / "h1.md"))
    assert code == 1 and res["ok"] is False and res["evidence_checkpoint_generic"] is True
    for phrase in ("lgtm", "all good", "ship it!", "wip", "good to go", "done deal"):
        (ws / "h2.md").write_text(_NO_EC.format(verif=f"- Evidence checkpoint: {phrase}"))
        res, code = run(capsys, "handoff_check", str(ws / "h2.md"))
        assert code == 1 and res["evidence_checkpoint_generic"] is True, phrase
    (ws / "h3.md").write_text(_NO_EC.format(
        verif="- Evidence checkpoint: confirmed — `tests/test_x.py::t` 0->1 passing"))
    res, code = run(capsys, "handoff_check", str(ws / "h3.md"))
    assert code == 0 and res["ok"] is True and res["evidence_checkpoint_ok"] is True


def test_handoff_evidence_checkpoint_concrete_accepted(ws, capsys):
    (ws / "ok.md").write_text(_NO_EC.format(
        verif="- Evidence checkpoint: confirmed — `tests/test_x.py::t` failed before, passed after"))
    res, code = run(capsys, "handoff_check", str(ws / "ok.md"))
    assert code == 0 and res["ok"] is True and res["evidence_checkpoint_ok"] is True


def test_handoff_over_length_warns_without_failing(ws, capsys):
    long_body = VALID_HANDOFF + "\n" + "\n".join(f"- detail {i}" for i in range(130))
    h = ws / "long.md"
    h.write_text(long_body)
    res, code = run(capsys, "handoff_check", str(h))
    assert code == 0 and res["ok"] is True
    assert res["line_warn"] is True and res["line_count"] > res["line_warn_threshold"]
