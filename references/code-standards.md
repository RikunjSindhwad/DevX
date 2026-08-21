# Code Standards

The language-agnostic quality bar. The implementer builds to it; the reviewer scores against it. Where
a repo has its own conventions (in `.devx/project.md`), those win for style — this is the floor.

## Definition of done — the quality gate
"Done" is not "tests pass". A project has **one reproducible quality-gate command** that runs, as
applicable: format check, lint, **type check**, the full test suite, a dependency audit, and a
package/build smoke. A task or workstream is complete only when that gate is green — or each gap is a
**written, explicit non-goal** in `.devx/decisions.md`, never silent.
- **No installed-but-unrun quality tools.** A type checker or auditor present in the dependencies
  (mypy, tsc, pip-audit, …) MUST be configured and pass — or be removed. "Present but never run" is a
  defect, not a quality story.
- **Skip-only is not evidence.** A packaging/integration test that skips when the artifact is absent
  proves nothing — build the artifact first, or run it where one is guaranteed.
- **Claims match artifacts.** Never state "all tests pass", "dependency-audited", "release-ready", or
  "chain-of-custody" in code, docs, or README unless the gate actually ran and the artifact actually
  does it. Use weaker language or build the real mechanism — never an aspirational claim.

## Correctness
- Handle the happy path **and** edge/error paths. Empty inputs, nulls, boundaries, failures.
- No swallowed errors. Catch narrowly, handle or propagate; never `except: pass` away a real failure.
- No race-prone shared mutable state without explicit synchronization.

## Tests
- **Test-first by default** (see `vault/testing/test-first-tdd.md`). Any test-after is declared.
- Deterministic: inject the clock, randomness, network, filesystem — don't depend on the real ones.
- One behavior per test; the name says the behavior; failures point at the cause.
- New code ships with tests for its acceptance criteria; existing suite stays green.
- **Negative paths required.** For every acceptance criterion implying a rejection/failure (invalid input, missing auth, quota exceeded, network error, conflict), write ≥1 test that proves the bad path is handled — not just the happy path.
- **Assertions must falsify.** An assertion that passes even when the criterion is broken is a non-test. Prefer `assert result == expected` over `assert result`; assert on the specific value/exception type, not just "it ran".
- **Realistic fixtures.** Fixtures resemble real inputs (a malformed sample, a boundary sample, a typical production sample) — not trivially perfect data the system would never receive.
- **Coverage is opt-in, not a target.** No universal threshold; tests must *confirm behavior*, not chase a line-%. If the project declares a coverage tool in `.devx/project.md`, the reviewer reports the changed-file delta; a new module shipping at very low coverage is a non-blocking finding unless justified.
- **No fake-proof tests.** A test that asserts only object construction, a private attribute, or a
  source literal (e.g. grepping the source for `--demo`) proves nothing — assert observable behavior.
  Where a criterion says "every X", test every X, not "at least one".
- **Fake ≠ end-to-end.** For tools depending on hardware or external systems, fake-runner/mock tests are
  not validation of the real thing — keep a validation matrix and label fake-only coverage honestly; a
  pending real-device/integration check is tracked, never implied done.

## Interactive UI controls
- **Every control is wired and reachable.** Each interactive control — button, menu, toggle, list row,
  dialog, language selector, save/export, start/stop — must be connected to a working handler and
  reachable through the UI. A rendered-but-unconnected control, or one permanently disabled with no
  enabling path, is a **blocking** defect.
- **Test through real user events.** Validate controls with real input events (`QTest.mouseClick`,
  Playwright `get_by_role().click()`, etc.), never by calling the slot/handler directly — a
  handler-only test does not satisfy the wiring criterion.

## Structure
- Small modules, **single responsibility**, one reason to change.
- Narrow interfaces; depend on abstractions, not concretions (see `vault/patterns/dependency-injection.md`).
- No dead code, no duplication (extract the third repetition), no commented-out blocks.
- **Reuse before create.** Before adding a new function, class, component, service, hook, route,
  schema/helper, API client, policy, config abstraction, or dependency, check whether the repo already
  has an equivalent that can be reused or extended. Prefer improving the existing owner when it only
  needs a small, coherent change. Creating a parallel implementation is a finding unless the plan records
  why the existing code is unsuitable.
- **Shared UI primitives.** Repeated button, field, alert, card/panel, badge/chip, table/list, modal, and
  form-control styling belongs in a shared UI layer once it appears in multiple places. The shared
  primitive owns sizing, wrapping, min-width, focus, disabled, loading, and accessibility behavior so
  screens do not drift or regress independently.
- **Canonical domain constants.** Repeated enum-like values, labels, status maps, verdict sets, source
  lists, permission presets, and date/format helpers belong in one domain/shared module. UI layers may
  own presentation labels, but they should not redefine canonical values.
- **Module & function size discipline.** Oversized files/functions are design smells. A *god-file*
  mixing more than one of {UI rendering, navigation, worker lifecycle, I/O, domain policy, persistence,
  external device/API calls} is a **blocking** structural failure even when tests pass. Use line count
  only as a soft prompt — a file past ~400 lines or a function past ~50 invites a split — but the
  blocking bar is the multi-responsibility god-file, not the raw line count.

## Naming & readability
- Names reveal intent; no `tmp`/`data2`/`doStuff`. Match the surrounding code's idiom.
- Functions short and focused; nesting shallow; early returns over deep `if` pyramids.

## User-facing strings
- **Externalize all user-facing text.** Every label, button, tooltip, error, empty state, status
  message, setting, and risk/domain label shown to a user lives in an external editable catalog or
  framework-native i18n — Qt `.ts`/`tr()`, gettext, a JSON/YAML bundle, or a single messages module —
  never hardcoded in logic. Introduce this from the **first UI phase**; copy changes must not require
  touching logic. (This is broader than parser output: it covers *all* user-facing strings.)

## Security & secrets
- No hardcoded secrets/keys/tokens. Read from env/secret store.
- Validate/parameterize all untrusted input (see `vault/security/owasp-top-10-quickref.md`).

## External boundaries — commands, errors, evidence
- **Type the failures.** Translate OS/process failures (timeout, missing binary, permission denied,
  non-zero exit) into typed domain errors at the boundary; raw `subprocess`/OS exceptions don't escape
  into callers. Keep distinct failures distinct — don't collapse "not found", "unauthorized", "timeout",
  and "parse error" into one opaque string the UI and logs can't tell apart.
- **Log every attempt.** A command/audit log records every external-command attempt — success AND
  failure/timeout/missing-binary — via a `finally` or a typed result, not only successful returns.
- **Validate every external token.** Every externally-sourced argv token (device serials, filenames,
  user input) is checked against an allowlist pattern and **rejects a leading `-`**, even when
  `shell=False` — option injection doesn't need a shell.
- **Enforce state preconditions.** A flow that requires a state (e.g. READY) raises a typed error on a
  bad state (e.g. OFFLINE) before issuing further commands — don't read the state and proceed anyway.
- **Integrity matches the claim.** If you claim chain-of-custody/audit, persist the raw artifacts + a
  manifest (in-memory ≠ custody) and include every recorded field in every export format. Parsers in
  audit/forensic domains surface what they dropped (counts/warnings/raw refs) — never silently discard
  source output.

## Dependencies
- Choose version policy by ecosystem and artifact. For apps, CLIs, services, toolchains, containers, and
  CI: commit a lockfile or exact pins so builds are reproducible. For published libraries: use compatible
  ranges where the ecosystem expects them, but pin dev/test tools and record the verified current version
  in `.devx/decisions.md`.
- Justify each new dependency (don't add one for a 10-line utility).
- Run the ecosystem's advisory check when adding deps (pip-audit / npm audit / govulncheck).

## Hygiene
- Run the project's formatter and linter; commit clean (no debug prints, no 0-byte files).
- Comments explain **why**, not what; keep them honest — a stale comment is a bug.

## Diagnosability (gated, runtime-shaped)
Canonical: `references/contracts/diagnosability.md`. A delivered runnable product must expose enough
structured, correlated evidence to reconstruct a failed operation; a library must preserve typed errors
and caller-owned logging hooks without configuring global logging. The plan selects the runtime shape and
proves its applicable floor. Scattered `print`s do not satisfy it and remain banned.

At minimum for the selected shape: native structured events with stable names/error codes, an appropriate
product verbosity control, operation/request/job correlation, meaningful lifecycle/external-attempt events,
one sanitized exception boundary, and tests for redaction/injection/correlation/failure behavior. Missing
applicable baseline diagnosability is blocking. OpenTelemetry, health endpoints, dashboards, support
bundles, and crash uploaders remain applicability-based—do not add them speculatively.

## Packaging & artifacts
- Prefer **minimal** bundle collection — explicit includes/excludes, not "collect everything" (smaller
  artifact, smaller attack/CVE surface); test that unwanted heavy modules/plugins are absent.
- Build outputs (`dist/`, `build/`, bundles) are **rebuilt, not source-controlled**; vendored binaries
  carry provenance + a hash.

## Finish clean
- Production code explains **current, non-obvious** behavior only. Build/phase narration — `Pxx`/`Txx`
  labels, `FP-FIX`, "MVP placeholder", one-device calibration notes — moves to docs/decisions/changelog
  before done.
- Remove dead or superseded code, views, and tests, or explicitly retain them for a named current use
  case. Don't ship parallel old/new flows "for completeness".
- **TODO discipline.** A `TODO`/`FIXME`/`HACK`/temporary marker is resolved now or promoted to
  `.devx/backlog.md` with a comment referencing the backlog ID. An untracked marker left in source is a
  finding.
- **Delete superseded code in-phase.** After a redesign or replacement, the superseded
  module/view/directory is deleted in the **same phase** that orphaned it. An unreferenced module is
  dead code even if it never appears in the additive diff.
- **Root cause, no masking layers.** A "fix" that adds a wrapper, broad `try/except`, default-fallback,
  or special-case to suppress a symptom — rather than correcting the originating logic — is not a fix.
