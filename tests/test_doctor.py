"""Tests for doctor (env preflight)."""
from helpers import dx, run, _which_present


def test_doctor_all_present_ok(capsys, monkeypatch):
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: True)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: True)
    monkeypatch.setattr(dx.shutil, "which", lambda name: "/usr/bin/" + name)
    res, code = run(capsys, "doctor")
    assert res["ok"] is True and code == 0 and res["missing_required"] == []
    by = {c["tool"]: c for c in res["checks"]}
    assert by["rg"]["status"] == "ok" and by["git"]["status"] == "ok"
    assert by["codebase-memory-mcp"]["status"] == "ok" and res["fts5"] is True


def test_doctor_missing_required_exits_nonzero_with_hint(capsys, monkeypatch):
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: True)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: False)
    monkeypatch.setattr(dx.shutil, "which", _which_present("apt-get", "git"))  # rg (required) absent
    res, code = run(capsys, "doctor")
    assert code == 1 and res["ok"] is False and "rg" in res["missing_required"]
    assert res["package_manager"] == "apt-get"
    assert any("ripgrep" in h for h in res["install_hints"])


def test_doctor_fts5_missing_is_degraded_not_blocking(capsys, monkeypatch):
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: False)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: True)
    monkeypatch.setattr(dx.shutil, "which", lambda name: "/usr/bin/" + name)
    res, code = run(capsys, "doctor")
    by = {c["tool"]: c for c in res["checks"]}
    assert by["sqlite3-fts5"]["status"] == "degraded"          # ripgrep fallback is a designed feature,
    assert "sqlite3-fts5" not in res["missing_required"]        # so a missing FTS5 must NOT block bootstrap
    assert res["ok"] is True and code == 0


def test_doctor_no_pkg_mgr(capsys, monkeypatch):
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: True)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: False)
    monkeypatch.setattr(dx.shutil, "which", lambda n: None)       # nothing present
    res, code = run(capsys, "doctor")
    assert res["package_manager"] is None and code == 1          # required git/rg missing → exit 1


def test_doctor_old_python(capsys, monkeypatch):
    fake_sys = type("S", (), {"version_info": (3, 10, 0)})()
    monkeypatch.setattr(dx.doctor, "sys", fake_sys)
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: True)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: True)
    monkeypatch.setattr(dx.shutil, "which", lambda n: "/usr/bin/" + n)
    res, code = run(capsys, "doctor")
    assert "python3" in res["missing_required"] and code == 1


def test_doctor_reports_uv_optional_with_installer_hint(capsys, monkeypatch):
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: True)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: False)
    monkeypatch.setattr(dx.shutil, "which", _which_present("apt-get", "git", "rg"))  # uv absent
    res, code = run(capsys, "doctor")
    by = {c["tool"]: c for c in res["checks"]}
    assert by["uv"]["required"] is False and by["uv"]["status"] == "optional-missing"
    assert any("astral.sh/uv" in h for h in res["install_hints"])     # special-cased installer, not apt-get
    assert "uv" not in res["missing_required"] and res["ok"] is True   # optional → never blocks


def test_doctor_reports_codebase_memory_mcp_optional_with_install_hint(capsys, monkeypatch):
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: True)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: False)
    monkeypatch.setattr(dx.shutil, "which", _which_present("apt-get", "git", "rg"))
    res, code = run(capsys, "doctor")
    by = {c["tool"]: c for c in res["checks"]}
    assert by["codebase-memory-mcp"]["required"] is False
    assert by["codebase-memory-mcp"]["status"] == "optional-missing"
    assert "codebase-memory-mcp" not in res["missing_required"]
    assert any("DeusData/codebase-memory-mcp" in h for h in res["install_hints"])
    assert res["ok"] is True and code == 0


def test_doctor_reports_security_scanners_degraded(capsys, monkeypatch):
    monkeypatch.setattr(dx.probes, "fts5_available", lambda: True)
    monkeypatch.setattr(dx.doctor, "_codebase_memory_mcp_present", lambda: False)
    monkeypatch.setattr(dx.shutil, "which", _which_present("apt-get", "git", "rg"))  # no scanners present
    res, code = run(capsys, "doctor")
    by = {c["tool"]: c for c in res["checks"]}
    assert by["pip-audit"]["status"] == "security-degraded" and by["pip-audit"]["required"] is False
    assert "pip-audit" in res["security_degraded"] and "gitleaks" in res["security_degraded"]
    assert res["ok"] is True and code == 0          # a missing scanner is visible, but NEVER blocks
