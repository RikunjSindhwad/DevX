"""Regression guards for the Markdown prompt/control-plane contracts."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ACTIVE_DIRS = ("agents", "references", "skills", "stages", "templates", "tools-guide")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _active_markdown() -> list[Path]:
    return [
        path
        for directory in ACTIVE_DIRS
        for path in (ROOT / directory).rglob("*.md")
    ]


def test_input_priority_trust_and_freshness_are_explicit():
    guide = _read("references/agent-guide.md")
    template = _read("templates/agent.template.md")

    assert "Hard invariant / approval boundary" in guide
    assert "untrusted evidence" in guide
    assert "MISSING_REQUIRED_INPUT" in guide
    assert "STALE_REQUIRED_INPUT" in guide
    assert "current primary source even when the vault has a non-empty result" in guide
    assert "| Source / trust | Missing or stale behavior |" in template


def test_browser_agent_cannot_provision_operator_runtime():
    browser = _read("agents/ui/browser.md")
    guide = _read("tools-guide/native/playwright.md")

    for text in (browser, guide):
        assert "SETUP_REQUIRED" in text
        assert "uv venv .devx/.venv" not in text
        assert "uv run --with playwright" not in text
    assert "uv pip install --python .devx/.venv" not in browser
    assert "operator-provisioned" in browser


def test_planning_contract_uses_writes_and_distinct_check_paths():
    designer = _read("agents/design/designer.md")
    plan_check = _read("references/contracts/plan-check.md")
    stage = _read("stages/03-plan.md")

    assert "Owns:" not in designer
    assert "Writes:" in designer
    assert ".devx/workstreams/{slug}/roadmap-check.md" in plan_check
    assert "critic_target=roadmap" in stage


def test_vcs_none_and_state_before_commit_are_explicit():
    stage03 = _read("stages/03-plan.md")
    stage04 = _read("stages/04-build.md")
    stage05 = _read("stages/05-document.md")

    assert "When it is `none`, skip all" in stage03
    assert stage04.index("### 6. Reconcile and advance durable state") < stage04.index(
        "### 7. Commit the completed phase"
    )
    assert "`none` → skip the git agent" in stage04
    assert "In VCS mode `none`, skip git" in stage05


def test_commit_kinds_and_ship_security_gate_are_defined():
    git_agent = _read("agents/vcs/git.md")
    ship = _read("stages/06-ship.md")

    for kind in ("phase", "docs", "final-state"):
        assert f"`commit_kind={kind}`" in git_agent
    assert "security-ship.md" in git_agent
    assert ship.index("commit_kind=final-state") < ship.index("devx:vcs:git op=pr")
    assert "operator security-risk acceptance" in ship


def test_parallel_fan_in_uses_exact_preallocated_handoffs():
    guide = _read("references/orchestrator-guide.md")
    build = _read("stages/04-build.md")
    explain = _read("skills/devx-explain/SKILL.md")

    assert "Parallel fan-in is exact and all-or-nothing" in guide
    assert "devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}" in guide
    assert "validate all expected handoffs" in build
    assert "Validate **both expected paths**" in build
    assert "Fan-in is all-or-nothing" in explain


def test_side_effect_reentry_and_pr_probe_are_explicit():
    guide = _read("references/orchestrator-guide.md")
    git_agent = _read("agents/vcs/git.md")
    ship = _read("stages/06-ship.md")

    assert "Probe before repeating side effects" in guide
    assert "git log -1" in git_agent and "git show --name-only HEAD" in git_agent
    probe = "gh pr view devx/{workstream} --json url,state"
    assert probe in git_agent
    assert git_agent.index(probe) < git_agent.index("gh pr create --base")
    assert "OPEN` → retain its URL and **skip `gh pr create`**" in git_agent
    assert "CLOSED/MERGED returns to the" in ship


def test_codex_second_opinion_is_inline_gated_and_advisory():
    skill = _read("skills/devx/SKILL.md")
    guide = _read("tools-guide/native/codex-review.md")
    orchestrator = _read("references/orchestrator-guide.md")

    assert "Bash(codex *)" in skill
    assert 'codex exec "prompt" -o output' in guide
    assert "--sandbox read-only" in guide and "--ephemeral" in guide
    assert '-o "{OUTPUT_PATH}"' in guide
    assert "AskUserQuestion" in guide and "Default to **decline**" in guide
    assert "never authoritative" in orchestrator.lower() or "another authority" in orchestrator.lower()
    assert "DevX does not wrap it in a command" in guide


def test_continuity_resumes_each_independent_lineage_with_fresh_fallback():
    skill = _read("skills/devx/SKILL.md")
    guide = _read("references/orchestrator-guide.md")
    build = _read("stages/04-build.md")
    verification = _read("references/contracts/phase-verification.md")

    assert "SendMessage" in skill
    assert "same-session optimization" in guide
    assert "Never persist an ephemeral agent id" in guide
    assert "resume the exact original `devx:build:implementer`" in build.lower()
    assert "resume the producing" in build
    assert "fresh regression checker" in verification
    assert "FIXED | SURVIVES | REGRESSION" in verification


def test_diagnosability_and_ui_quality_are_runtime_scoped_and_enforced():
    diagnostics = _read("references/contracts/diagnosability.md")
    ui = _read("references/ui-design.md")
    plan = _read("templates/plan-phase.template.md")
    reviewer = _read("agents/review/reviewer.md")
    browser = _read("agents/ui/browser.md")
    scout = _read("agents/recon/scout.md")

    for shape in ("library/package", "CLI", "browser/frontend", "service/API", "worker/pipeline"):
        assert shape in diagnostics
    assert "This is not a new DevX flag" in diagnostics
    assert "log-diagnosis.md" in diagnostics and "diagnose-logs" in scout
    assert "Missing applicable baseline" in reviewer and "[BLOCKING]" in reviewer
    assert "Product Interface Direction" in ui and "subjective numeric design scores" in ui
    assert "1440px" in browser and "375px" in browser and "computed" in browser
    assert "Diagnostics applicability" in plan and "Product Interface Direction" in plan


def test_docs_research_memory_backlog_and_promotion_contracts():
    docs = _read("agents/docs/docs.md")
    explain = _read("skills/devx-explain/SKILL.md")
    researcher = _read("agents/research/researcher.md")
    backlog = _read("templates/backlog.template.md")
    active_text = "\n".join(path.read_text(encoding="utf-8") for path in _active_markdown())

    assert "| workstream | yes, every mode |" in docs
    assert "return_as={NN}-docs-map-{component}.md" in explain
    assert "current primary source" in researcher
    assert "it does not move items between sections" in backlog
    assert "devx validate --promote-to" not in active_text
    assert "Refusal-grade" not in active_text


def test_prompt_eval_corpus_has_required_coverage_and_valid_paths():
    cases = json.loads(_read("tests/evals/cases.json"))
    required_categories = {
        "input-contract",
        "trust-boundary",
        "freshness",
        "runtime-ownership",
        "vcs-routing",
        "durable-state",
        "security-gate",
        "handoff-identity",
        "plan-check",
        "memory-hygiene",
        "commit-kind",
        "ship-sequencing",
        "fan-in-barrier",
        "side-effect-reentry",
        "external-review",
        "agent-continuity",
        "diagnosability",
        "ui-quality",
    }

    assert len(cases) == len({case["id"] for case in cases})
    assert required_categories <= {case["category"] for case in cases}
    for case in cases:
        assert case["prompt"].strip()
        assert case["expected"]
        assert case["forbidden"]
        for relative in case["evidence_files"]:
            assert (ROOT / relative).is_file(), f"{case['id']}: missing {relative}"
