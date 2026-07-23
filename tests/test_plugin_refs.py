"""Plugin reference-integrity guard.

Catches **stale intra-plugin references** (a deleted/renamed file, a removed agent, a moved path) the
moment the plugin is edited — so DevX keeps its own "no stale reference" property mechanically, in tests,
instead of relying on a manual sweep. Three checks, scoped to avoid false positives on the curated
vault's illustrative example paths and on changelog-style history:

1. every `${CLAUDE_PLUGIN_ROOT}/<path>` reference resolves to a real file/dir (the var is unambiguously
   this plugin) — checked everywhere except `vault/` (illustrative examples);
2. every `devx:<role>:<name>` agent-dispatch reference resolves to `agents/<role>/<name>.md`;
3. every bare structural reference (`stages|agents|.../<file>.md|py|sh|json`) resolves — checked in the
   **active operating files** + README/ARCHITECTURE (the "current-state" docs), with a tiny allow-list
   for the pentest plugin DevX is compared against.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # the plugin root (devx/)

# The web-pentest-expert plugin DevX was modeled on — named in ARCHITECTURE's "taken from" comparison,
# not a DevX file. (Add here only if a comparison genuinely references another external plugin file.)
EXTERNAL_ALLOWLIST = {"skills/scan/SKILL.md"}

ACTIVE_DIRS = ("stages", "agents", "skills", "references", "templates", "tools-guide")

ROOT_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`)>,;\"']+)")
BARE_RE = re.compile(
    r"(?<![\w./-])(?:stages|agents|references|templates|tools-guide|skills|hooks|scripts)/"
    r"[\w./-]+\.(?:md|py|sh|json)")
AGENT_RE = re.compile(r"devx:([a-z]+):([a-z0-9-]+)")


def _rel_parts(p):
    return p.relative_to(ROOT).parts


def _all_md():
    return [p for p in ROOT.rglob("*.md")
            if "vault" not in _rel_parts(p)
            and ".devx" not in _rel_parts(p)]


def _active_md():
    md = [p for d in ACTIVE_DIRS for p in (ROOT / d).rglob("*.md")]
    md += [ROOT / "README.md", ROOT / "ARCHITECTURE.md"]
    return [p for p in md if p.exists()]


def _lines(files):
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            yield rel, i, line


def _clean(p):
    return p.rstrip("`).,;:")


def test_plugin_root_paths_resolve():
    bad = []
    for rel, i, line in _lines(_all_md()):
        for m in ROOT_RE.finditer(line):
            p = _clean(m.group(1))
            if "{" in p or "*" in p or p.endswith("/"):
                continue
            if not (ROOT / p).exists():
                bad.append(f"{rel}:{i}  ${{CLAUDE_PLUGIN_ROOT}}/{p}")
    assert not bad, "dangling ${CLAUDE_PLUGIN_ROOT} references:\n" + "\n".join(bad)


# obvious placeholder tokens in prose (e.g. `devx:role:name`) — never real agent role/name pairs, so a
# doc using them as an illustrative form must not trip the guard. (Real roles/names never collide here.)
_PLACEHOLDERS = {"role", "name", "slug", "agent", "type"}


def test_agent_dispatch_refs_resolve():
    bad = []
    for rel, i, line in _lines(_all_md()):
        for role, name in AGENT_RE.findall(line):
            if role in _PLACEHOLDERS or name in _PLACEHOLDERS:
                continue
            if not (ROOT / "agents" / role / f"{name}.md").exists():
                bad.append(f"{rel}:{i}  devx:{role}:{name} -> agents/{role}/{name}.md")
    assert not bad, "dangling agent-dispatch references (renamed/removed agent?):\n" + "\n".join(bad)


def test_bare_structural_refs_resolve():
    bad = []
    for rel, i, line in _lines(_active_md()):
        for raw in BARE_RE.findall(line):
            p = _clean(raw)
            if "{" in p or "*" in p or p in EXTERNAL_ALLOWLIST:
                continue
            if not (ROOT / p).exists():
                bad.append(f"{rel}:{i}  {p}")
    assert not bad, "dangling structural references in active files:\n" + "\n".join(bad)
