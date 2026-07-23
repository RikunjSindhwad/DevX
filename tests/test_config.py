"""Tests for path helpers: _within / vault_dir."""
from pathlib import Path

from helpers import dx


# --- H-01: userConfig precedence ---
def test_vault_dir_prefers_plugin_option(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_VAULT_PATH", str(tmp_path / "opt"))
    monkeypatch.setenv("DEVX_VAULT_PATH", str(tmp_path / "env"))
    assert dx.vault_dir() == (tmp_path / "opt").resolve()


# --- H-02: promote-to path traversal is blocked ---
def test_within_blocks_escape(tmp_path):
    v = tmp_path / "vault"; v.mkdir()
    assert dx._within(v / "a" / "b.md", v)
    assert not dx._within(v / ".." / "x.md", v)
    assert not dx._within(Path("/etc/passwd"), v)
