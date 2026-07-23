#!/usr/bin/env python3
"""DevX hook: token-usage / cost tracker.

Reads the PostToolUse hook event JSON from stdin, parses the session transcript JSONL (plus any
sub-agent transcripts), and emits a per-model cost breakdown table via `systemMessage`.

Fires on: PostToolUse for sub-agent dispatches — so after every agent call you see the cost so far.
Stdlib-only (json/re/sys/pathlib); safe to run with plain `python3`.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

# Per-MTok pricing (USD). Base input rate is the anchor; output is explicit; cache rates are derived
# via the multipliers below. Approximate — verified 2026-07 against
# https://platform.claude.com/docs/en/about-claude/pricing (re-check when a new family/version ships).
# A tier here = a price row; resolve_tier() maps any model ID (any version) to one of these.
PRICING = {
    #                    base_input  output
    "fable":            {"input": 10.0,  "output": 50.0},   # Fable 5
    "mythos":           {"input": 10.0,  "output": 50.0},   # Mythos 5 (limited availability) — same rate as Fable
    "opus-4.5+":        {"input": 5.0,   "output": 25.0},   # Opus 4.5–4.8
    "opus-4.0":         {"input": 15.0,  "output": 75.0},   # Opus 4 / 4.1 (deprecated/retired)
    "sonnet":           {"input": 3.0,   "output": 15.0},   # Sonnet 4.x and Sonnet 5 standard rate
    "sonnet-5-intro":   {"input": 2.0,   "output": 10.0},   # Sonnet 5 introductory — date-gated in resolve_tier
    "haiku-4.5":        {"input": 1.0,   "output": 5.0},
    "haiku-3.5":        {"input": 0.80,  "output": 4.0},
    "haiku-3":          {"input": 0.25,  "output": 1.25},
}

# Sonnet 5 launched at introductory $2/$10; standard $3/$15 takes effect the day after. resolve_tier
# date-gates this so the estimate is right today and self-corrects to the standard rate after the cutoff.
_SONNET5_INTRO_END = date(2026, 8, 31)

CACHE_5M_MULTIPLIER = 1.25
CACHE_1H_MULTIPLIER = 2.0
CACHE_READ_MULTIPLIER = 0.1
FAST_MODE_MULTIPLIER = 2.0   # Opus 4.8 fast mode = 2x base ($10/$50 vs $5/$25). (Deprecated Opus 4.7 fast was 6x.)
USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read",
    "cache_write_5m",
    "cache_write_1h",
    "cost_usd",
    "messages",
)


def _parse_version(model_name: str, family: str) -> tuple[int, int]:
    pat = re.search(family + r"[- ]?(\d+)[.\-](\d+)", model_name)
    if pat:
        return int(pat.group(1)), int(pat.group(2))
    pat = re.search(r"(\d+)[.\-](\d+)[- ]?" + family, model_name)
    if pat:
        return int(pat.group(1)), int(pat.group(2))
    pat = re.search(family + r"[- ]?(\d+)", model_name)
    if pat:
        return int(pat.group(1)), 0
    return 0, 0


def resolve_tier(model_name: str, today: date | None = None) -> str:
    if not model_name:
        return "sonnet"
    m = str(model_name).lower()
    if "opus" in m:
        major, minor = _parse_version(m, "opus")
        if major >= 5 or (major == 4 and minor >= 5):
            return "opus-4.5+"
        return "opus-4.0"
    if "haiku" in m:
        major, minor = _parse_version(m, "haiku")
        if major >= 5 or (major == 4 and minor >= 5):
            return "haiku-4.5"
        if major == 3 and minor >= 5:
            return "haiku-3.5"
        return "haiku-3"
    if "fable" in m:
        return "fable"
    if "mythos" in m:
        return "mythos"
    # Sonnet: v5 has temporary introductory pricing (self-corrects to standard after the cutoff).
    major, _ = _parse_version(m, "sonnet")
    if major >= 5 and (today or date.today()) <= _SONNET5_INTRO_END:
        return "sonnet-5-intro"
    return "sonnet"      # any Sonnet + last-resort default for an unrecognized family (add new families above)


def display_model(model_name: str) -> str:
    """Compact display label that preserves the actual version used."""
    if not model_name:
        return "unknown"
    m = str(model_name).lower().replace("claude-", "")
    m = re.sub(r"\[.*?\]", "", m)
    for family in ("opus", "sonnet", "haiku", "fable", "mythos"):
        pat = re.search(family + r"[- ]?(\d+)[.\-](\d+)", m)
        if pat:
            return f"{family}-{pat.group(1)}.{pat.group(2)}"
        pat = re.search(r"(\d+)[.\-](\d+)[- ]?" + family, m)
        if pat:
            return f"{family}-{pat.group(1)}.{pat.group(2)}"
        pat = re.search(family + r"[- ]?(\d+)", m)       # single-major, e.g. sonnet-5 / fable-5
        if pat:
            return f"{family}-{pat.group(1)}"
        if family in m:
            return family
    return m[:24]


def empty_usage(model: str = "") -> dict:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_write_5m": 0,
        "cache_write_1h": 0,
        "cost_usd": 0.0,
        "messages": 0,
        "model": model,
    }


def _usage_key(obj: dict, msg: dict, line_no: int) -> tuple[str, str | int]:
    """Stable key for streamed transcript records. Claude Code can append multiple JSONL snapshots
    for the same assistant message while streaming; they share message.id/requestId — count the
    latest snapshot once instead of charging every snapshot."""
    if msg.get("id"):
        return ("message", msg["id"])
    if obj.get("requestId"):
        return ("request", obj["requestId"])
    if obj.get("uuid"):
        return ("uuid", obj["uuid"])
    return ("line", line_no)


def _message_usage(model: str, usage: dict) -> dict:
    tier = resolve_tier(model)
    rates = PRICING[tier]
    base_in = rates["input"]
    out_rate = rates["output"]

    if usage.get("speed") == "fast":
        base_in *= FAST_MODE_MULTIPLIER
        out_rate *= FAST_MODE_MULTIPLIER

    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0

    cache_creation = usage.get("cache_creation", {}) or {}
    if not isinstance(cache_creation, dict):
        cache_creation = {}
    c5m = cache_creation.get("ephemeral_5m_input_tokens", 0) or 0
    c1h = cache_creation.get("ephemeral_1h_input_tokens", 0) or 0
    total_cw = usage.get("cache_creation_input_tokens", 0) or 0
    if c5m == 0 and c1h == 0 and total_cw > 0:
        c5m = total_cw

    cost = (
        inp * base_in / 1_000_000
        + out * out_rate / 1_000_000
        + cache_read * base_in * CACHE_READ_MULTIPLIER / 1_000_000
        + c5m * base_in * CACHE_5M_MULTIPLIER / 1_000_000
        + c1h * base_in * CACHE_1H_MULTIPLIER / 1_000_000
    )

    return {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_read": cache_read,
        "cache_write_5m": c5m,
        "cache_write_1h": c1h,
        "cost_usd": cost,
        "messages": 1,
        "model": display_model(model),
        "raw_model": model,
    }


def _add_usage(dst: dict, src: dict) -> None:
    for key in USAGE_KEYS:
        dst[key] += src.get(key, 0)


def parse_usage_by_model(jsonl_path: Path) -> dict[str, dict]:
    records: dict[tuple[str, str | int], dict] = {}
    if not jsonl_path.is_file():
        return {}

    with open(jsonl_path) as f:
        for line_no, line in enumerate(f, 1):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict) or "usage" not in msg:
                continue
            usage = msg["usage"]
            if not isinstance(usage, dict):
                continue
            model = msg.get("model") or ""
            records[_usage_key(obj, msg, line_no)] = _message_usage(model, usage)

    by_model: dict[str, dict] = {}
    for record in records.values():
        label = record["model"]
        bucket = by_model.setdefault(label, empty_usage(label))
        _add_usage(bucket, record)
    return by_model


def parse_usage(jsonl_path: Path) -> dict:
    by_model = parse_usage_by_model(jsonl_path)
    totals = sum_usage(list(by_model.values())) if by_model else empty_usage()
    totals["models"] = by_model
    totals["model"] = ", ".join(by_model.keys())
    return totals


def collect_subagents(session_dir: Path) -> list[dict]:
    sa_dir = session_dir / "subagents"
    if not sa_dir.is_dir():
        return []
    agents = []
    for meta_path in sorted(sa_dir.glob("*.meta.json")):
        agent_id = meta_path.stem.replace(".meta", "")
        jsonl_path = sa_dir / f"{agent_id}.jsonl"
        meta = {}
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            pass
        usage = parse_usage(jsonl_path)
        usage["agent_id"] = agent_id
        usage["agent_type"] = meta.get("agentType", "unknown")
        usage["description"] = meta.get("description", "")
        agents.append(usage)
    return agents


def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def sum_usage(rows: list[dict]) -> dict:
    out = empty_usage()
    for row in rows:
        _add_usage(out, row)
    return out


def merge_model_usage(*model_maps: dict[str, dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for model_map in model_maps:
        for label, usage in model_map.items():
            bucket = merged.setdefault(label, empty_usage(label))
            _add_usage(bucket, usage)
    return merged


def models_from_usage(usage: dict) -> dict[str, dict]:
    models = usage.get("models")
    if isinstance(models, dict):
        return models
    if any(usage.get(key, 0) for key in USAGE_KEYS):
        label = usage.get("model") or "unknown"
        row = empty_usage(label)
        _add_usage(row, usage)
        return {label: row}
    return {}


def build_table(main_usage: dict, subagents: list[dict]) -> str:
    model_maps = [models_from_usage(main_usage)]
    model_maps.extend(models_from_usage(agent) for agent in subagents)
    by_model = merge_model_usage(*model_maps)
    used_models = [
        usage for usage in by_model.values()
        if usage["input_tokens"] or usage["output_tokens"]
        or usage["cache_read"] or usage["cache_write_5m"] or usage["cache_write_1h"]
    ]
    grand = sum_usage(used_models)
    cache_w = lambda u: u["cache_write_5m"] + u["cache_write_1h"]

    hdr = f"{'Model':16s} {'Msgs':>5s} {'Input':>8s} {'Output':>8s} {'Cache R':>8s} {'Cache W':>8s} {'Cost':>9s}"
    sep = "-" * len(hdr)

    def row(label: str, u: dict) -> str:
        cost = f"${u['cost_usd']:.2f}"
        return (
            f"{label[:16]:16s} {fmt(u['messages']):>5s} "
            f"{fmt(u['input_tokens']):>8s} {fmt(u['output_tokens']):>8s} "
            f"{fmt(u['cache_read']):>8s} {fmt(cache_w(u)):>8s} "
            f"{cost:>9s}"
        )

    BOLD, DIM, GREEN, CYAN, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[36m", "\033[0m"
    lines = [f"{DIM}devx · token usage / cost (this session){RESET}",
             f"{DIM}{hdr}{RESET}", f"{DIM}{sep}{RESET}"]
    for usage in used_models:
        lines.append(f"{CYAN}{row(usage['model'], usage)}{RESET}")
    lines.append(f"{DIM}{sep}{RESET}")
    if len(used_models) > 1:
        lines.append(f"{BOLD}{GREEN}{row('total', grand)}{RESET}")
    elif not used_models:
        lines.append("No token usage found.")
    return "\n".join(lines)


def main():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        json.dump({"continue": True}, sys.stdout)
        return

    transcript_path = Path(event.get("transcript_path", ""))
    session_id = event.get("session_id", "")
    if not transcript_path.is_file():
        json.dump({"continue": True}, sys.stdout)
        return

    session_dir = transcript_path.parent / session_id
    main_usage = parse_usage(transcript_path)
    subagents = collect_subagents(session_dir)
    table = build_table(main_usage, subagents)
    json.dump({"continue": True, "systemMessage": table}, sys.stdout)


if __name__ == "__main__":
    main()
