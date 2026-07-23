"""Environment preflight for /devx:devx-init. Required tools must be present (else DevX can't run); optional
ones degrade gracefully (code graph MCP → rg/ast-grep, web search → native, FTS5 → ripgrep). Returns JSON + per-tool
install commands for the detected OS package manager; exits non-zero (via the router) on a missing
REQUIRED tool. FTS5 is strongly recommended but NOT required (the ripgrep fallback is a designed feature).
"""
from __future__ import annotations

import shutil
import sys
import os
from pathlib import Path

from lib import probes

DOCTOR_TOOLS = [   # (tool, required, why)
    ("git", True, "version control + change review"),
    ("rg", True, "ripgrep — live source discovery + kb_search fallback"),
    ("codebase-memory-mcp", False, "preferred code graph MCP for reuse/dedup discovery before writing code"),
    ("ast-grep", False, "structure-aware source search and safe AST rewrites"),
    ("ugrep", False, "long-line-safe search (minified/bundled files)"),
    ("gh", False, "github_search code search + PRs (remote VCS mode)"),
    ("sqlite3", False, "sqlite CLI (optional; python's sqlite3 module is the real dependency)"),
    ("uv", False, "fast isolated Python env (dev/test + optional fetch extras) — keeps installs out of system Python"),
]
_PKG_MGRS = [   # (binary, install template) — first present manager wins
    ("apt-get", "sudo apt-get install -y {pkg}"),
    ("brew", "brew install {pkg}"),
    ("dnf", "sudo dnf install -y {pkg}"),
    ("pacman", "sudo pacman -S --noconfirm {pkg}"),
    ("zypper", "sudo zypper install -y {pkg}"),
    ("apk", "sudo apk add {pkg}"),
]
_PKG_NAMES = {
    "git": {"apt-get": "git", "brew": "git", "dnf": "git", "pacman": "git", "zypper": "git", "apk": "git"},
    "rg": {"apt-get": "ripgrep", "brew": "ripgrep", "dnf": "ripgrep", "pacman": "ripgrep", "zypper": "ripgrep", "apk": "ripgrep"},
    "ast-grep": {"apt-get": "ast-grep", "brew": "ast-grep", "dnf": "ast-grep", "pacman": "ast-grep", "zypper": "ast-grep", "apk": "ast-grep"},
    "ugrep": {"apt-get": "ugrep", "brew": "ugrep", "dnf": "ugrep", "pacman": "ugrep", "zypper": "ugrep", "apk": "ugrep"},
    "gh": {"apt-get": "gh", "brew": "gh", "dnf": "gh", "pacman": "github-cli", "zypper": "gh", "apk": "github-cli"},
    "sqlite3": {"apt-get": "sqlite3", "brew": "sqlite", "dnf": "sqlite", "pacman": "sqlite", "zypper": "sqlite3", "apk": "sqlite"},
}


SECURITY_TOOLS = [   # (tool, ecosystem, why) — dep-audit + secret scanners used by the security agent.
    ("pip-audit", "python", "Python dependency known-vuln audit"),
    ("osv-scanner", "any", "cross-ecosystem dependency audit (fallback when no ecosystem tool)"),
    ("gitleaks", "any", "secret scan over the working tree / git history"),
    ("npm", "javascript", "npm audit — JS/Node dependency audit"),
    ("cargo", "rust", "cargo audit — Rust dependency audit"),
    ("govulncheck", "go", "Go dependency known-vuln audit"),
]   # absence = "security-degraded" (a visible gap), NEVER a hard requirement — never blocks bootstrap.


def _codebase_memory_mcp_present() -> bool:
    if shutil.which("codebase-memory-mcp"):
        return True
    env_bin = os.environ.get("CODEBASE_MEMORY_MCP_BIN")
    if env_bin and os.access(env_bin, os.X_OK):
        return True
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return False
    root = Path(plugin_root)
    candidates = [
        root / ".devx" / "tools" / "codebase-memory-mcp",
        root.parent / ".local" / "bin" / "codebase-memory-mcp",
        Path.home() / ".local" / "bin" / "codebase-memory-mcp",
    ]
    return any(p.is_file() and os.access(p, os.X_OK) for p in candidates)


def _detect_pkg_mgr():
    for binary, tmpl in _PKG_MGRS:
        if shutil.which(binary):
            return binary, tmpl
    return None, None


def cmd_doctor(args) -> dict:
    mgr, tmpl = _detect_pkg_mgr()
    pyver = ".".join(map(str, sys.version_info[:3]))
    py_ok = sys.version_info >= (3, 11)
    fts5 = probes.fts5_available()
    checks = [
        {"tool": "python3", "present": True, "required": True,
         "status": "ok" if py_ok else "degraded", "version": pyver,
         "why": "the retrieval library runtime (need ≥3.11)"},
        {"tool": "sqlite3-fts5", "present": fts5, "required": False,
         "status": "ok" if fts5 else "degraded",
         "why": "FTS5 powers fast ranked kb_search; if ABSENT, kb_search degrades to ripgrep "
                "(slower, unranked) — strongly recommended, but not a hard requirement"},
    ]
    hints = []
    for tool, required, why in DOCTOR_TOOLS:
        present = _codebase_memory_mcp_present() if tool == "codebase-memory-mcp" else shutil.which(tool) is not None
        status = "ok" if present else ("missing" if required else "optional-missing")
        entry = {"tool": tool, "present": present, "required": required, "status": status, "why": why}
        if not present:
            if tool == "uv":                         # uv isn't in most distro repos — use its own installer
                entry["install"] = "curl -LsSf https://astral.sh/uv/install.sh | sh   (or: pipx install uv)"
                hints.append(entry["install"])
            elif tool == "codebase-memory-mcp":
                entry["install"] = ("Run `${CLAUDE_PLUGIN_ROOT}/bin/install-codebase-memory-mcp` "
                                    "or install a verified release binary from "
                                    "https://github.com/DeusData/codebase-memory-mcp/releases/latest.")
                hints.append(entry["install"])
            else:
                pkg = _PKG_NAMES.get(tool, {}).get(mgr) if mgr else None
                if pkg:
                    entry["install"] = tmpl.format(pkg=pkg)
                    hints.append(entry["install"])
        checks.append(entry)
    sec_degraded = []
    for tool, eco, why in SECURITY_TOOLS:
        present = shutil.which(tool) is not None
        checks.append({"tool": tool, "present": present, "required": False, "ecosystem": eco,
                       "status": "ok" if present else "security-degraded", "why": why})
        if not present:
            sec_degraded.append(tool)
    missing_required = [c["tool"] for c in checks if c["required"] and c["status"] == "missing"]
    if not py_ok:
        missing_required.append("python3")
    return {"ok": not missing_required, "python": pyver, "fts5": fts5, "package_manager": mgr,
            "checks": checks, "missing_required": missing_required, "install_hints": hints,
            "security_degraded": sec_degraded}
