#!/usr/bin/env python3
"""PreToolUse model-budget guard for initial Agent dispatches — the pre-dispatch counterpart to the
SubagentStop token_monitor (which reports cost after initial and resumed rounds). It enforces
orchestrator-guide §6: the entire opus-escalation budget is reviewer / designer / security.
If the orchestrator passes an opus model override for any OTHER agent, this blocks the dispatch
before it spends and tells it to re-read §6.

Degrades to a SILENT ALLOW whenever the model is not inspectable on this event (some harness
versions resolve the subagent model after PreToolUse) or stdin is malformed — it only ever blocks
when it can positively see an opus override for a non-qualifying role, so it never false-blocks.

stdlib-only; reads the PreToolUse JSON on stdin.
"""
from __future__ import annotations

import json
import sys

# orchestrator-guide §6 — the only roles that may be escalated to opus.
# `designer` is the merged brainstormer+architect+planner agent (opus on hard greenfield design).
VALID_OPUS_ROLES = frozenset({"reviewer", "designer", "security"})


def _emit(obj):
    if obj:
        print(json.dumps(obj))
    sys.exit(0)


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        _emit(None)                                   # malformed stdin → allow (degrade)
    if event.get("tool_name") != "Agent":
        _emit(None)
    ti = event.get("tool_input") or {}
    model = str(ti.get("model") or "")
    if "opus" not in model.lower():                   # no opus override (or model not exposed) → allow
        _emit(None)
    role = str(ti.get("subagent_type") or "").split(":")[-1].lower()
    if role in VALID_OPUS_ROLES:                       # a qualifying §6 escalation → allow + remind
        _emit({"systemMessage":
               f"[model-guard] opus dispatch for '{role}' — confirm it is a qualifying §6 case "
               f"(reviewer high-risk/complex phase / hard-greenfield designer (architect mode) / critical-or-deep security)."})
    _emit({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason":
            f"[model-guard] Refused opus for '{role or 'agent'}'. Only reviewer/designer (architect mode)/security "
            f"may escalate to opus (orchestrator-guide §6) — re-read §6 and dispatch at sonnet."}})


if __name__ == "__main__":
    main()
