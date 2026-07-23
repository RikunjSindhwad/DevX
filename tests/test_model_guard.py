"""Tests for hooks/model_guard.py — the PreToolUse opus-budget guard.

The hook is a stdlib-only filter that reads the PreToolUse JSON on stdin and either stays silent
(allow), emits a systemMessage (allow + §6 reminder), or emits a permissionDecision:"deny". These
tests drive it exactly as the harness does: as a subprocess, feeding the event JSON on stdin and
inspecting stdout. It always exits 0 (it signals via JSON, never a non-zero code).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "hooks" / "model_guard.py"


def _run(event):
    """Run the guard with `event` (dict or raw str) on stdin; return the CompletedProcess."""
    payload = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def _parse(proc):
    """Parse the guard's stdout as JSON, or return None when it stayed silent (allow)."""
    out = proc.stdout.strip()
    return json.loads(out) if out else None


# --- deny: opus for a maker role ---
def test_opus_maker_role_denied():
    proc = _run({"tool_name": "Agent",
                 "tool_input": {"model": "claude-opus-4-8", "subagent_type": "devx:build:implementer"}})
    assert proc.returncode == 0
    obj = _parse(proc)
    hso = obj["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["hookEventName"] == "PreToolUse"
    assert "implementer" in hso["permissionDecisionReason"]


# --- future-proofing: enforcement matches the model FAMILY, not a pinned version ---
def test_opus_denied_across_alias_and_future_versions():
    # bare alias, current pinned IDs, and hypothetical future versions must all be caught,
    # so a new Sonnet/Opus/Haiku release never silently slips an opus maker past the guard.
    for model in ("opus", "claude-opus-4-8", "claude-opus-5", "claude-opus-6-1", "Claude-OPUS-99"):
        proc = _run({"tool_name": "Agent",
                     "tool_input": {"model": model, "subagent_type": "devx:build:implementer"}})
        assert proc.returncode == 0, model
        obj = _parse(proc)
        assert obj and obj.get("hookSpecificOutput", {}).get("permissionDecision") == "deny", model


# --- allow + reminder: opus for each valid §6 role ---
def test_opus_valid_roles_allowed_with_reminder():
    for role in ("devx:review:reviewer", "devx:design:designer", "devx:security:security"):
        proc = _run({"tool_name": "Agent",
                     "tool_input": {"model": "claude-opus-4-8", "subagent_type": role}})
        assert proc.returncode == 0, role
        obj = _parse(proc)
        assert obj is not None, role
        assert "systemMessage" in obj, role
        assert "hookSpecificOutput" not in obj, role          # reminder, NOT a deny


# --- allow (silent): sonnet, or no model field ---
def test_sonnet_allowed_silently():
    proc = _run({"tool_name": "Agent",
                 "tool_input": {"model": "claude-sonnet-4-5", "subagent_type": "devx:build:implementer"}})
    assert proc.returncode == 0
    assert _parse(proc) is None


def test_missing_model_allowed_silently():
    proc = _run({"tool_name": "Agent",
                 "tool_input": {"subagent_type": "devx:build:implementer"}})
    assert proc.returncode == 0
    assert _parse(proc) is None


# --- allow: non-Agent tool, or malformed stdin ---
def test_non_agent_tool_allowed():
    proc = _run({"tool_name": "Bash",
                 "tool_input": {"model": "claude-opus-4-8", "command": "ls"}})
    assert proc.returncode == 0
    assert _parse(proc) is None


def test_malformed_stdin_allowed():
    proc = _run("this is not json {{{")
    assert proc.returncode == 0
    assert _parse(proc) is None


def test_empty_stdin_allowed():
    proc = _run("")
    assert proc.returncode == 0
    assert _parse(proc) is None
