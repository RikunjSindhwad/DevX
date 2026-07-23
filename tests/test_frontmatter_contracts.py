"""Static guards for Claude plugin surfaces that strict validation does not fully police."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AGENT_TOOLS = {"Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"}
AGENT_COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.relative_to(ROOT)} has no YAML frontmatter"
    return text.split("---", 2)[1]


def _list_items(frontmatter: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*$", frontmatter)
    if not match:
        return []
    items = []
    for line in frontmatter[match.end():].splitlines():
        if not line.strip():
            continue
        item = re.match(r"^  -\s+(.+?)\s*$", line)
        if item:
            items.append(item.group(1))
            continue
        if not line.startswith(" "):
            break
    return items


def test_commands_directory_contains_no_accidental_markdown_commands():
    command_files = sorted((ROOT / "commands").rglob("*.md")) if (ROOT / "commands").exists() else []
    assert not command_files, (
        "every commands/*.md file is discoverable; move prose/README files elsewhere: "
        + ", ".join(str(path.relative_to(ROOT)) for path in command_files)
    )


def test_agent_tools_are_exact_base_names_or_exact_mcp_tools():
    bad = []
    for path in sorted((ROOT / "agents").glob("*/*.md")):
        for tool in _list_items(_frontmatter(path), "tools"):
            if tool in AGENT_TOOLS:
                continue
            if tool.startswith("mcp__") and "*" not in tool and "(" not in tool:
                continue
            bad.append(f"{path.relative_to(ROOT)}: {tool}")
    assert not bad, "argument-shaped, wildcard, or unknown agent tools:\n" + "\n".join(bad)


def test_agent_colors_use_the_documented_enum():
    bad = []
    for path in sorted((ROOT / "agents").glob("*/*.md")):
        match = re.search(r"(?m)^color:\s*(\S+)\s*$", _frontmatter(path))
        if not match or match.group(1) not in AGENT_COLORS:
            bad.append(f"{path.relative_to(ROOT)}: {match.group(1) if match else '<missing>'}")
    assert not bad, "invalid agent colors:\n" + "\n".join(bad)


def test_skill_frontmatter_avoids_known_inert_or_overbroad_entries():
    bad = []
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        frontmatter = _frontmatter(path)
        if re.search(r"(?m)^memory:", frontmatter):
            bad.append(f"{path.relative_to(ROOT)}: memory is an agent field, not a skill field")
        for tool in _list_items(frontmatter, "allowed-tools"):
            if tool.startswith("Write("):
                bad.append(f"{path.relative_to(ROOT)}: inert Write path preapproval: {tool}")
            if tool.startswith("mcp__") and "*" in tool:
                bad.append(f"{path.relative_to(ROOT)}: MCP wildcard: {tool}")
    assert not bad, "invalid skill frontmatter:\n" + "\n".join(bad)


def test_plugin_command_hooks_use_exec_form():
    data = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    bad = []
    for event, groups in data["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                if hook.get("type") == "command" and not isinstance(hook.get("args"), list):
                    bad.append(f"{event}/{group.get('matcher', '*')}: {hook.get('command')}")
    assert not bad, "command hooks must use explicit args arrays (exec form):\n" + "\n".join(bad)
