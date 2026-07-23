"""Tests for the vault maintenance surface (`devx vault stats` — layout distribution + split signal)."""
from helpers import dx, run, requires_fts5


def _mk(ws, rel, body="# T\nbody\n"):
    p = ws / "vault" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_vault_stats_counts_and_subfolders(ws, capsys):
    _mk(ws, "patterns/retry-backoff.md")
    _mk(ws, "patterns/resilience/circuit-breaker.md")   # one level of sub-folder
    _mk(ws, "patterns/resilience/bulkhead.md")
    _mk(ws, "languages/python/asyncio.md")
    res, code = run(capsys, "vault", "stats")
    assert code == 0 and res["ok"] is True and res["total_files"] == 4
    cats = {c["category"]: c for c in res["categories"]}
    assert cats["patterns"]["files"] == 3 and cats["patterns"]["direct"] == 1
    sub = {s["name"]: s for s in cats["patterns"]["subfolders"]}
    assert sub["resilience"]["files"] == 2
    assert cats["languages"]["direct"] == 0 and cats["languages"]["files"] == 1


def test_vault_stats_flags_oversized_flat_category(ws, capsys):
    for i in range(4):
        _mk(ws, f"patterns/p{i}.md")
    res, _ = run(capsys, "vault", "stats", "--split-threshold", "3")   # 4 direct > 3 → flagged
    cats = {c["category"]: c for c in res["categories"]}
    assert cats["patterns"]["oversized"] is True
    assert any("patterns/" in s for s in res["split_suggestions"])


def test_vault_stats_no_split_signal_when_under_threshold(ws, capsys):
    _mk(ws, "testing/fakes.md")
    _mk(ws, "testing/fixtures.md")
    res, _ = run(capsys, "vault", "stats")          # default threshold 20
    assert res["split_suggestions"] == []
    assert all(c["oversized"] is False for c in res["categories"])


def test_vault_stats_flags_oversized_subfolder(ws, capsys):
    for i in range(5):
        _mk(ws, f"languages/python/m{i}.md")
    res, _ = run(capsys, "vault", "stats", "--split-threshold", "4")
    assert any("languages/python/" in s for s in res["split_suggestions"])


def test_vault_usage_when_no_action(ws, capsys):
    res, _ = run(capsys, "vault")
    assert res["ok"] is False and "usage" in res["error"]


@requires_fts5
def test_vault_stats_enriches_with_index_counts(ws, capsys):
    _mk(ws, "patterns/retry.md", "# Retry\nbody\nSee [[other]].\n")
    dx.main(["index", "--scope", "vault"]); capsys.readouterr()
    res, _ = run(capsys, "vault", "stats")
    assert res["indexed"]["files"] == 1 and res["indexed"]["chunks"] >= 1
    assert res["indexed"]["links"] == 1               # the [[other]] wikilink
