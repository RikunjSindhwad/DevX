---
id: test-first-tdd
title: Test-First Development (TDD) — Working Patterns
type: testing
tags: [testing, tdd, acceptance-criteria]
summary: The red-green-refactor loop and when autonomous agents should use test-first versus declared exceptions.
related:
  - {slug: dependency-injection, rel: see-also}
created: 2026-06-20
---

# Test-First Development (TDD) — Working Patterns

Curated guidance. Language-agnostic. Pair with `tools-guide/test-runners/` for runner specifics.

## The loop
1. **Red** — write the smallest failing test that encodes one acceptance criterion. Run it; confirm it fails for the *right* reason (assertion, not import error).
2. **Green** — write the least code that makes it pass. No gold-plating.
3. **Refactor** — clean names, remove duplication, keep tests green.

## Why test-first beats test-after for autonomous agents
- Acceptance criteria become **executable and pre-committed** before implementation, so the bar cannot be moved to match whatever got built.
- The failing→passing transition is concrete evidence the code does something real.
- An independent reviewer can re-run the same tests in a clean context — self-graded "looks correct" is unreliable.

## What makes a good unit test
- One behavior per test; name says the behavior (`returns_401_when_token_expired`).
- Arrange / Act / Assert, no branching in the test body.
- Deterministic: no real clock, network, or randomness — inject them.
- Fails with a message that points at the cause.

## When test-first does NOT fit (declare the exception)
Spikes/exploration, pure scaffolding/config, and hard-to-unit-test integration glue. There, write a **characterization test after** or rely on integration/manual verification — but say so explicitly in the handoff Verification section so the reviewer judges by the right bar.

## Test pyramid
Many fast unit tests, fewer integration tests, very few end-to-end. Push logic down so it can be unit-tested; keep e2e for critical user journeys only.

> Source: DevX curated knowledge · curated · 2026-06-20
