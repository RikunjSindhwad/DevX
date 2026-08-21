"""Tests for hooks/token_monitor.py — the SubagentStop cost/usage tracker.

Focus on pricing-tier resolution and a cost calc, so a new model family (Fable, Mythos, a future
Sonnet/Opus/Haiku) is priced from its own rate instead of silently falling through to the Sonnet row.
Stdlib-only module loaded directly (no side effects at import; main() is __main__-guarded).
"""
import importlib.util
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("token_monitor", ROOT / "hooks" / "token_monitor.py")
tm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tm)


def test_resolve_tier_covers_every_family_and_version():
    cases = {
        "claude-opus-4-8": "opus-4.5+",
        "claude-opus-4-5": "opus-4.5+",
        "claude-opus-5":   "opus-4.5+",     # future opus → newest tier, not the old $15 row
        "claude-opus-4-1": "opus-4.0",
        "claude-opus-4":   "opus-4.0",
        "claude-sonnet-4-6": "sonnet",
        "claude-sonnet-5":   "sonnet",      # post-intro: standard sonnet tier (see date-gated test below)
        "claude-haiku-4-5": "haiku-4.5",
        "claude-haiku-3-5": "haiku-3.5",
        "claude-haiku-3":   "haiku-3",
        "claude-fable-5":   "fable",        # previously mispriced as sonnet
        "claude-mythos-5":  "mythos",       # previously mispriced as sonnet
        "":                    "sonnet",    # empty → safe default
        "some-unknown-model":  "sonnet",    # unrecognized family → last-resort default
    }
    post_intro = date(2027, 1, 1)   # after the Sonnet-5 introductory window, so mappings are the enduring ones
    for model, tier in cases.items():
        assert tm.resolve_tier(model, today=post_intro) == tier, model
        assert tier in tm.PRICING, tier


def test_sonnet5_introductory_pricing_is_date_gated():
    assert tm.resolve_tier("claude-sonnet-5", today=date(2026, 7, 15)) == "sonnet-5-intro"  # during intro
    assert tm.resolve_tier("claude-sonnet-5", today=date(2026, 9, 1)) == "sonnet"           # after cutoff
    assert tm.resolve_tier("claude-sonnet-4-6", today=date(2026, 7, 15)) == "sonnet"        # only v5 gets intro
    assert tm.PRICING["sonnet-5-intro"] == {"input": 2.0, "output": 10.0}


def test_fable_and_mythos_priced_at_own_rate_not_sonnet():
    # 1M input + 1M output at $10/$50 = $60 — NOT the $18 the sonnet fallback used to give.
    for model in ("claude-fable-5", "claude-mythos-5"):
        row = tm._message_usage(model, {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
        assert round(row["cost_usd"], 2) == 60.0, model


def test_opus_and_sonnet_cost_calc():
    opus = tm._message_usage("claude-opus-4-8", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
    assert round(opus["cost_usd"], 2) == 30.0            # $5 + $25
    sonnet = tm._message_usage("claude-sonnet-4-6", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
    assert round(sonnet["cost_usd"], 2) == 18.0          # $3 + $15 (Sonnet 4.6 standard, date-independent)


def test_display_model_labels_families_with_version():
    assert tm.display_model("claude-fable-5") == "fable-5"
    assert tm.display_model("claude-mythos-5") == "mythos-5"
    assert tm.display_model("claude-sonnet-5") == "sonnet-5"      # not bare "sonnet"
    assert tm.display_model("claude-opus-4-8") == "opus-4.8"


def test_count_rounds_excludes_tool_results(tmp_path):
    transcript = tmp_path / "agent-abc.jsonl"
    rows = [
        {"type": "user", "message": {"role": "user", "content": "Initial task"}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}
        ]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "Resume and recheck"}
        ]}},
    ]
    transcript.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert tm.count_rounds(transcript) == 2


def test_build_table_shows_subagent_continuity_and_cache_ratio():
    agent = tm.empty_usage("sonnet-5")
    agent.update({
        "agent_id": "agent-12345678",
        "agent_type": "devx:review:reviewer",
        "rounds": 2,
        "messages": 3,
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read": 900,
        "cost_usd": 0.01,
        "models": {"sonnet-5": {
            **tm.empty_usage("sonnet-5"),
            "messages": 3,
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_read": 900,
            "cost_usd": 0.01,
        }},
    })
    table = tm.build_table(tm.empty_usage(), [agent])
    assert "continuity by subagent" in table
    assert "review:reviewer" in table
    assert "12345678" in table
    assert "90.0%" in table
