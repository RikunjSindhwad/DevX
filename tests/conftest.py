"""Make `import devx_lib` work from the tests without installing anything."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Also put the tests/ directory on the path so `from helpers import ...` works.
TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import pytest


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A clean workspace: cwd=tmp, an empty vault wired via DEVX_VAULT_PATH, a .devx dir."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vault").mkdir()
    monkeypatch.setenv("DEVX_VAULT_PATH", str(tmp_path / "vault"))
    (tmp_path / ".devx").mkdir()
    return tmp_path
