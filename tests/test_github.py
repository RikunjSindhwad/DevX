"""Tests for github_search."""
import json

from helpers import dx, run


def test_github_search_without_gh(ws, capsys, monkeypatch):
    monkeypatch.setattr(dx.shutil, "which", lambda name: None)
    res, _ = run(capsys, "github_search", "foo")
    assert res["ok"] is False and "gh" in res["error"].lower()


def test_github_search_success_parses_json(ws, capsys, monkeypatch):
    monkeypatch.setattr(dx.shutil, "which", lambda n: "/usr/bin/gh")
    payload = json.dumps([{"repository": "o/r", "path": "x.py", "url": "http://x", "textMatches": []}])
    monkeypatch.setattr(dx.subprocess, "run",
                        lambda *a, **k: type("P", (), {"stdout": payload, "stderr": "", "returncode": 0})())
    res, _ = run(capsys, "github_search", "needle", "--kind", "code")
    assert res["ok"] is True and res["kind"] == "code" and res["count"] == 1


def test_github_search_token_env_and_error(ws, capsys, monkeypatch):
    monkeypatch.setattr(dx.shutil, "which", lambda n: "/usr/bin/gh")
    monkeypatch.delenv("GH_TOKEN", raising=False); monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_GITHUB_TOKEN", "tok123")
    monkeypatch.setattr(dx.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    res, _ = run(capsys, "github_search", "q")
    assert res["ok"] is False and "error" in res                 # token mapped, then subprocess raised
