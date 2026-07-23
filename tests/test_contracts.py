"""Single-source guard for the canonical contract files.

The phase-verification policy (severity tiers, verify-band sequence, bounded fix-pass rule, correctness floor,
commit gate, independence) and the plan-check policy (who checks a plan, what it challenges, verdict,
dependency reconciliation, re-baseline) each live in ONE canonical file under `references/contracts/`.
Every stage/agent/skill *points* there instead of restating them — that is what stops the policy drift
we refactored away (severity tiers were once defined in 3 files; plan-CHECK routing in 5).

This test makes the "define once" property mechanical: a distinctive canonical definition phrase must
appear in exactly its contract file among the active operating docs — so a future edit cannot silently
re-duplicate the policy. It also checks each contract is actually referenced (not orphaned). Scoped to
the active operating dirs (like test_plugin_refs), so narrative/changelog mentions don't false-trigger.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_DIRS = ("stages", "agents", "references", "skills", "templates")

# (distinctive canonical phrase, the ONE active file it may appear in)
CANONICAL = [
    ("exactly one of: **fix**", "references/contracts/phase-verification.md"),          # §V1 [IMPORTANT]
    ("housekeeping/style", "references/contracts/phase-verification.md"),                # §V1 [NOTE]
    ("never audit code", "references/contracts/phase-verification.md"),                  # §V2 sequence
    ("self-graded by the context that produced it", "references/contracts/plan-check.md"),  # §P1
    ("loosen a test in place", "references/contracts/plan-check.md"),                    # §P5 re-baseline
]

CONTRACTS = [
    "references/contracts/phase-verification.md",
    "references/contracts/plan-check.md",
]


def _active_md():
    md = [p for d in ACTIVE_DIRS for p in (ROOT / d).rglob("*.md")]
    return [p for p in md if p.exists()]


def test_canonical_policy_defined_once():
    files = _active_md()
    bad = []
    for phrase, home in CANONICAL:
        hits = sorted(p.relative_to(ROOT).as_posix()
                      for p in files if phrase in p.read_text(encoding="utf-8"))
        if hits != [home]:
            bad.append(f"{phrase!r}\n    expected only in [{home}]\n    found in {hits}")
    assert not bad, ("canonical contract policy was duplicated or moved (re-drift):\n"
                     + "\n".join(bad))


def test_contracts_are_referenced_not_orphaned():
    files = _active_md()
    bad = []
    for c in CONTRACTS:
        refs = [p.relative_to(ROOT).as_posix() for p in files
                if p.relative_to(ROOT).as_posix() != c and c in p.read_text(encoding="utf-8")]
        if not refs:
            bad.append(f"{c} is referenced by no consumer (orphaned contract)")
    assert not bad, "\n".join(bad)
