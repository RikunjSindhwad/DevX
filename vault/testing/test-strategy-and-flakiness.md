---
id: test-strategy-and-flakiness
title: Test Strategy & Flakiness
type: testing
tags: [testing, test-strategy, flakiness, integration-testing, contract-testing, test-data, pyramid, tdd]
summary: How to choose the right test shape (pyramid, trophy, honeycomb) for your system, place tests at the right level, manage test data safely, apply contract testing at service boundaries, and systematically eliminate flaky tests.
related:
  - {slug: test-first-tdd, rel: see-also}
  - {slug: dependency-injection, rel: see-also}
  - {slug: ci-cd-and-deployment, rel: see-also}
created: 2026-06-20
---

# Test Strategy & Flakiness

Choosing what to test at which level — and keeping that suite reliable — matters more than any
individual testing technique. This entry focuses on strategy and reliability; for the red-green-refactor
loop that populates that suite see [[test-first-tdd]].

## Test-shape models

**Test Pyramid** (Fowler / Cohn): many unit tests at the base, fewer integration tests in the middle,
very few end-to-end tests at the top. Fast feedback, low cost. The rule of thumb: push logic down to the
level where it can be exercised in-process with no real I/O.

**Testing Trophy** (Kent C. Dodds): shifts weight toward integration tests on the premise that tests
closest to real usage give the highest confidence-per-dollar. Unit tests still handle complex pure
logic; e2e tests cover critical paths only.

**Honeycomb** (Spotify model for services): most tests are service-level integration tests that exercise
a single service with its real data layer but no downstream dependencies. It keeps very few
component/contract tests at boundaries and minimal e2e. Suits microservice fleets where unit tests
become trivial or mock-heavy.

**Choosing:** if your domain logic is complex and pure (calculations, transformations, rules engines),
lean pyramid. If your code is mostly glue between frameworks and stores, lean trophy or honeycomb. The
key metric is test value-to-maintenance ratio, not a ratio of test counts.

## What to put at each level

| Level | Test when… | Avoid when… |
|---|---|---|
| **Unit** | Logic has multiple branches, pure functions, algorithms, policy rules | The "unit" is just wiring two library calls together |
| **Integration** | You must verify how components talk to a real DB, queue, or filesystem | The integration path is trivially simple or already covered by a contract test |
| **End-to-end** | A critical user journey spans multiple services or browsers | You are repeating logic already covered at a lower level |

Keep e2e tests narrow and stable. Every e2e test is a maintenance liability; treat adding one as a small architectural decision.

## Test-data management

Poor test data is one of the leading causes of flakiness and coupling between tests.

- **Factories over fixtures:** generate minimal valid objects programmatically (factory functions / builder patterns). Fixtures (static files or seed scripts) drift out of sync with the schema and create invisible coupling.
- **Isolate per test:** each test creates and owns its data; no test reads data created by another.
  In-memory SQLite is appropriate when SQLite is production or the adapter behavior is intentionally
  faked. Database-specific integration claims require the production engine/version family.
- **Transactional teardown:** rollback is fast when all work shares the test transaction. It does not
  cover independently committed connections, background workers, or the transaction behavior itself;
  use engine-appropriate cleanup or isolated schemas/databases for those cases.
- **Seeding for e2e:** maintain a minimal canonical seed that represents the system's baseline state.
  Give each test isolated identities/records or reset at a granularity that prevents order dependence;
  a suite-only reset is acceptable only when tests cannot mutate shared seed state. Document the seed.
- **Sensitive/production data:** never copy production data into test environments. Anonymize or synthesize using the same factories.

## Contract testing at service boundaries

When two services communicate, integration tests that spin up both together are slow, brittle, and hard to run in CI. Contract testing solves this by capturing the exact messages each side expects and verifying each side in isolation.

- **Consumer-driven contracts:** the consumer defines what it needs from the provider; the provider
  verifies it fulfills every registered consumer contract. A provider change that would break a consumer
  fails the provider's CI before the change ships. Tools that implement this: Pact (see source).
- **Schema registries:** for event-driven systems, publish message schemas to a registry; producers and consumers validate against it in CI. This is a weaker but cheaper form of contract testing.
- **Do not skip contracts in favor of a shared integration environment.** Shared environments serialize test runs, make root-cause analysis harder, and create the "works in staging, breaks in prod" failure mode.

## Flakiness: causes and mitigations

A flaky test is one that passes and fails on the same code. It erodes trust in the entire suite faster than any other test-quality problem.

**Async / timing races**
- Root cause: `sleep(N)` calls, polling with a hard timeout, or assertions that fire before an async side-effect completes.
- Mitigation: wait for an observable state change (poll with backoff until condition, not until time elapsed); expose synchronization hooks in the system under test; keep async code testable by [[dependency-injection]] of the scheduler.

**Shared mutable state**
- Root cause: global singletons, static caches, module-level registries mutated by one test and read by another.
- Mitigation: reset shared state in `beforeEach`/`setUp`; prefer instance-scoped objects; lint for global mutation in test setup.

**Test-order dependence**
- Root cause: test A leaves a side-effect that test B silently relies on.
- Mitigation: run tests in a randomized order in CI (most modern runners support this); fix failures discovered by randomization, do not lock the order.

**Network and external services**
- Root cause: tests call real third-party APIs; latency or rate-limits cause sporadic failures.
- Mitigation: stub at the network layer (recorded responses, local fake servers); reserve real network calls for a small, explicitly-tagged contract or smoke-test suite that runs less frequently.

**File-system and environment pollution**
- Root cause: tests write to shared temp paths or read from paths that differ by machine.
- Mitigation: use per-test temp directories; make all paths configurable rather than hardcoded; clean up in `afterEach` even on failure (use `finally`/`defer`).

**Flakiness triage workflow:** quarantine only when needed to restore a trustworthy required signal,
and attach an owner, issue, visible reporting, and deadline. Retry-on-failure may collect diagnostic
evidence but must not convert a flaky required check into a silent pass. Fix, replace, or delete
quarantined tests promptly; track quarantine age and count as reliability debt.

## Strategy checkpoints

1. Write down the test strategy for a feature before writing tests — which level, what data approach, any contract boundaries.
2. Track flakiness rate per suite in [[ci-cd-and-deployment]] pipelines; alert when it exceeds a threshold (e.g. >1% of runs).
3. Treat a slow test suite the same as slow production code: profile it, eliminate unnecessary real I/O, parallelize where safe.

> Source: https://martinfowler.com/articles/practical-test-pyramid.html · curated · 2026-06-20
