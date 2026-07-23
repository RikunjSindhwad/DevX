# Contract: Phase Verification

**Canonical, single source** for finding severity, the verify-band sequence, the bounded fix-pass rule, the
correctness floor, the git commit-refusal gate, and checker independence. Stages, agents, the skill, and
templates **point here** — they do not restate these definitions. If a rule here changes, it changes in
one place. (Plan-time checks live in `plan-check.md`; the handoff/evidence/logging contract lives in
`agent-guide.md`; quality-bar definitions live in `code-standards.md`.)

## §V1 — Finding severity tiers (the canonical definitions)
Every review/security finding is tagged with exactly one tier:

- **`[BLOCKING]`** — must be fixed before PASS/commit. Any acceptance criterion unmet, a hardcoded
  secret, a test regression, a happy-path correctness bug, an unwired/dead interactive control, a
  god-file (a module mixing >1 of {UI render, navigation, worker lifecycle, I/O, domain policy,
  persistence, external device/API}), or an **undocumented loosened test / relaxed goal-level success
  criterion** (see `plan-check.md` re-baseline rule).
- **`[IMPORTANT]`** — non-blocking, but the orchestrator **MUST action every one before commit** via
  exactly one of: **fix** it · **downgrade** it with explicit evidence · **deliberately defer** it with
  a `.devx/backlog.md` link and a `DECISION`. A valid deferral names the source artifact/finding id,
  owner phase/workstream, priority, reason, and closure condition; otherwise it is still
  undispositioned. This is **not** a silent demotion to `[NOTE]` or an unprioritized backlog. Covers: a
  user-visible behavior named in the brief (even if not an explicit criterion), a security finding
  below Critical/High, a band-aid-over-root-cause, and module-size / debuggability /
  string-externalization / shared-token / orphan-module / untracked-TODO findings.
- **`[NOTE]`** — housekeeping/style/refactor with no user-visible impact; may be batched or deferred
  freely.

An **acceptance-criteria failure is always `[BLOCKING]`**, even if it looks minor.

## §V2 — The verify band runs in sequence, not one parallel fan-out
Per phase, after implement:

1. **3a — functional code review FIRST** (`devx:review:reviewer`, the cheapest gate). If it `REJECT`s or
   leaves a surviving `[BLOCKING]`, fix and re-review **before** spending on the rest.
2. **3b — once 3a PASSes**, on the **stabilized diff**: `devx:ui:browser` (only if a UI changed) +
   `devx:security:security`. These two may run **in parallel with each other**.
3. **fix** the 3b findings, then **re-verify** by re-dispatching a **fresh** verify band (a fresh
   reviewer; security/ui only if they had findings).

Security may run inside **3a** only for a **security-critical** phase with high early-design risk.
Rationale: security/UI must never audit code that a pending review will rewrite.

## §V3 — One FIX pass per verification return
Each rejected verification return gets at most **one** implementer pass before re-verification.
Functional review (3a) is one return. After it passes, parallel UI and security checks (3b) may be
consolidated as a second return. The fixer applies the assigned finding set in one pass, then **re-runs the
exact gate the verify band recorded** — the `Command:` / `Verify (live):` lines in
`review.md`/`security.md`/`gui.md` — and **quotes the real output**; a weaker substitute run or a
self-reported "green" does **not** close a finding. Fixes address the **root cause** — a wrapper, broad
`try/except`, default-fallback, or special-case that only suppresses a symptom is **not** a fix
(`agent-guide.md` §4). If a correctness-floor issue survives its bounded pass, **escalate** — do not
ping-pong with the same checker.

## §V4 — Correctness floor + the commit chokepoint
**Correctness floor** (never ship broken): a `REJECT` verdict, a surviving `[BLOCKING]`, or a surviving
**Critical/High** security finding stops automated progression and gates the operator. A `REJECT` or
`[BLOCKING]` functional failure must be retried, re-scoped through the goal/scope gate, or aborted; it
cannot be risk-accepted as passing. A Critical/High security finding should be fixed. If the operator
explicitly accepts that security risk, record the finding id, rationale, approver/date, and scope in
`.devx/decisions.md`, plus a `.devx/backlog.md` follow-up with owner/reason/closure condition.

**The git agent is the sole committer and the chokepoint that makes the floor stick.** Before committing a
phase it Reads that phase's `review.md` + `security.md` and **REFUSES to commit** when any of these holds:

- the review verdict is `REJECT`,
- an unresolved `[BLOCKING]` finding remains,
- an `[IMPORTANT]` finding is left **undispositioned** — not fixed, not downgraded-with-evidence, not
  deferred-with-`.devx/backlog.md`-link+`DECISION` (if a disposition can't be confirmed, refuse and
  surface),
- a **Critical/High** security finding survives without the explicit security-risk acceptance record
  described above.

On refusal it does not commit — it surfaces the exact failing gate via `### Orchestrator requests` and
returns; the **orchestrator owns the operator gate**.

## §V5 — Checker independence
Every checker (the code reviewer, security) runs in a **fresh context** with no memory of how the artifact
was made, and judges against the **pre-committed acceptance criteria** — never the maker's rationale or
self-justification. A checker acts only on objective findings in its inputs; it **never fabricates or
attributes operator feedback** that isn't there. (The independent check of a *plan* is the designer
plan-CRITIC — see `plan-check.md`.)
