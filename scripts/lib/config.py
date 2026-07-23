"""Vault/DB path resolution + the path-containment guard. Shared by retrieval and validate."""
from __future__ import annotations

import os
from pathlib import Path

DB_NAME = "mdvault-devx.sqlite"


def vault_dir() -> Path:
    # precedence: userConfig (CLAUDE_PLUGIN_OPTION_VAULT_PATH) > env override > plugin-root default
    root = (os.environ.get("CLAUDE_PLUGIN_OPTION_VAULT_PATH")
            or os.environ.get("DEVX_VAULT_PATH")
            or (Path(os.environ.get("CLAUDE_PLUGIN_ROOT", ".")) / "vault"))
    return Path(root).resolve()


def db_path() -> Path:
    return vault_dir() / DB_NAME


def _within(child: Path, parent: Path) -> bool:
    """True iff `child` resolves to `parent` or a path beneath it. Blocks `../` traversal,
    absolute-path escape, and symlink escape (resolve() collapses all three)."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
