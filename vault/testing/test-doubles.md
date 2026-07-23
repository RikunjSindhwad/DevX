---
id: test-doubles
title: Test Doubles — Mocks, Stubs, Fakes, and When to Use Each
type: testing
tags: [testing, mocks, stubs, fakes, spies, dummies, test-doubles, tdd, over-mocking, london-school, detroit-school]
summary: The precise vocabulary of test doubles (dummy/stub/spy/mock/fake), when each is appropriate, and the over-mocking trap that makes tests fragile and meaningless.
related:
  - {slug: test-strategy-and-flakiness, rel: relates-to}
  - {slug: test-first-tdd, rel: relates-to}
  - {slug: dependency-injection, rel: see-also}
created: 2026-06-21
---

# Test Doubles — Mocks, Stubs, Fakes, and When to Use Each

"Mock" is the most overloaded word in testing. Practitioners use it to mean any stand-in for a real
collaborator — but the precise vocabulary established by Gerard Meszaros and popularized by Martin
Fowler identifies five distinct types of test double. Getting the taxonomy right prevents the single
most common test-design mistake: mocking everything and coupling tests to implementation details instead
of behavior. For when to use test doubles at each level of the pyramid see [[test-strategy-and-flakiness]];
for the red-green-refactor loop that produces them see [[test-first-tdd]].

## Taxonomy (Meszaros / Fowler)

A **test double** is the generic term for any object that replaces a real production collaborator during
a test. The term comes from "stunt double" — it stands in so the SUT (system under test) doesn't have
to interact with the real thing. There are five precise subtypes:

**Dummy**
Passed to the SUT to satisfy a parameter signature but never actually used by the code path under test.
A `null` cast to an interface or an empty no-op object. The test does not care about this collaborator
at all — it just needs the constructor call to succeed.

**Stub**
Provides canned, pre-programmed return values to calls the SUT makes during the test. A stub does not
assert anything; it only supplies controlled input. Used to put the SUT into a particular state
(e.g., "the repository returns an empty list") without running the real implementation. Stubs never
fail a test on their own.

**Spy**
A stub that also records how it was called — which methods were invoked, with what arguments, how many
times. The test asserts on those records after the exercise phase. A spy is the lightest-weight way to
check outbound calls when you still want the real collaborator's behavior for the main path.

**Mock**
Pre-programmed with **expectations** before the exercise phase. A mock verifies during (or immediately
after) the call that the expected interactions occurred — and fails the test immediately if an unexpected
call arrives or an expected one is missed. Mocks are the only double type whose verification is
behavioral (did the right calls happen?) rather than state-based (did the system end up in the right
state?). Mocking frameworks (Mockito, unittest.mock, Moq, Jest's `jest.fn`) primarily produce mocks.

**Fake**
A working, in-process implementation with shortcuts that make it unsuitable for production. An
in-memory database, an in-process message queue, an in-memory email sink. Unlike stubs, fakes execute
real logic — they are just simpler or faster than the production version. A fake must be maintained
alongside the real implementation; it can go stale.

### Quick reference

| Double | Has real logic? | Fails the test? | Records calls? |
|---|---|---|---|
| Dummy | No | No | No |
| Stub | No | No | No |
| Spy | Partial | No (only via assertion) | Yes |
| Mock | No | Yes (on wrong interaction) | Yes |
| Fake | Yes (simplified) | Only via assertions | No |

## Mocks vs Stubs — the state/behavior divide

Fowler's key insight in "Mocks Aren't Stubs": these two types represent **fundamentally different
verification styles**.

**State verification (stubs, fakes):** exercise the SUT, then assert that the resulting state of the
SUT or its collaborators is correct. "After calling `order.fill(warehouse)`, `order.isFilled()` is
true and `warehouse.inventory("Talisker")` dropped by 50." The test doesn't care which internal calls
happened — only the observable outcome.

**Behavior verification (mocks):** assert that the SUT made specific calls to specific collaborators
in specific ways. "The mailer's `send()` method was called exactly once with the right address." The
test cares about *how* the result was produced, not just *what* was produced.

This split maps onto two TDD schools:

- **Detroit / classicist school**: prefer real objects and state verification; use test doubles only
  to isolate against slow/non-deterministic collaborators (filesystems, networks, clocks). Unit tests
  can include multiple real objects — the "unit" is a behavior, not a class.

- **London / mockist school**: mock every collaborator; unit tests are strictly one-class. Drives
  interface design through tests (TDD as design tool), but risks coupling tests to the implementation
  details of how objects collaborate.

Neither school is categorically wrong. The Detroit approach is safer against refactoring; the London
approach is more useful when driving out interfaces in green-field code. Most teams blend: real
objects for fast in-process collaborators, doubles for I/O and external systems.

## When to use each

**Dummy** — the collaborator is irrelevant to the specific behavior under test but the SUT's API
requires it. Do not invest in a full stub.

**Stub** — you need a dependency to return a controlled value (list of users, a timestamp, an error)
so the SUT can exercise a particular code path. The test is about the SUT's response to that input,
not about whether the dependency was called.

**Fake** — the real implementation is too slow, stateful, or complex for unit/integration tests, but
you need realistic behavior (not just a canned return). Use an in-memory DB for tests that exercise
real query logic; use an in-process queue to test producers and consumers together without a broker.
Fakes give higher confidence than stubs when the logic of the collaborator itself matters.
See [[test-strategy-and-flakiness]] on in-process databases.

**Mock** — the test is specifically about *whether* a call was made and *with what arguments*. Examples:
did the payment gateway's `charge()` get called with the right amount? Did the audit logger receive an
entry for every state change? Reserve mocks for cases where the outbound call is the behavior — not
just a side-effect of reaching the right state.

**Spy** — you want to assert that a call happened but you also want the collaborator to run its real
implementation for most of the test. Useful for wrapping a real dependency you don't fully control
(e.g., wrapping a logger to assert it emitted a specific message while still letting it write).

## The over-mocking trap

Over-mocking is the most common test-design failure: mocking every collaborator regardless of whether
the test cares about the interaction. Symptoms:

- **10:1 mock-to-real-code ratio**: tests spend more lines setting up mocks than asserting behavior.
- **Tests that pass when the feature is broken**: the mock always returns success, so the test can
  never catch a real integration failure.
- **Tests that fail when the feature is correct**: renaming a method or reordering internal calls
  breaks dozens of tests that should still pass. The implementation changed; the behavior didn't.
- **Every refactor requires mock updates**: internal restructuring — moving logic between private
  methods, extracting a helper — is invisible to users but visible to every mock that verified those
  calls.

The root cause: mocks verify *how* the SUT works internally, not *what* it delivers to the outside
world. Coupling tests to implementation detail is the opposite of what tests are for.

**Remedies:**

1. **Mock at system boundaries, not between internal classes.** Collaborators that cross a process
   boundary (HTTP, DB, filesystem, clock, random) are legitimate doubles targets. Classes inside the
   same module/package are usually not.
2. **Prefer fakes for slow dependencies.** An in-memory DB tests the real query logic without the
   latency penalty. A fake eliminates the mock fragility *and* improves test coverage.
3. **Use state verification by default.** If you can express the test as "given X input, the output
   is Y state", do so. Add behavior verification (mocks/spies) only when the outbound call *is* the
   requirement (e.g., "the email must be sent").
4. **Heuristic**: if a mock's setup is longer than the assertion, the test is probably testing the
   wrong thing.

## Integration test boundary

At some layer, use the real thing. Mocking a DB adapter while testing business logic creates a false
sense of security: the business logic test passes, but nothing has verified that the queries actually
work against the real schema. Use SQLite in-memory when SQLite is the production engine or when an
intentional adapter fake is covered by contract tests. For PostgreSQL/MySQL-specific SQL, types,
constraints, transactions, and locking, run integration tests against the same engine/version family
(often an ephemeral container). Embedded brokers/fakes are useful only when their documented semantics
match what the test is claiming. Reserve end-to-end tests for critical user journeys across real
service boundaries.

> Source: https://martinfowler.com/articles/mocksArentStubs.html · promoted by /devx:devx-vault · 2026-06-21
