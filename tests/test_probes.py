"""Tests for fts5_available."""


def test_fts5_available_returns_bool():
    from lib import probes
    assert isinstance(probes.fts5_available(), bool)


def test_probes_degrade_on_failure(monkeypatch):
    from lib import probes
    import sqlite3 as _sq
    monkeypatch.setattr(probes.sqlite3, "connect",
                        lambda *a, **k: (_ for _ in ()).throw(_sq.OperationalError("no fts5")))
    assert probes.fts5_available() is False                      # OperationalError → False
