---
id: concurrency-and-async
title: Concurrency and Asynchronous Programming Patterns
type: pattern
tags: [concurrency, async, data-race, deadlock, atomicity, idempotency, async-await, thread-safety, locking, event-loop]
summary: Language-agnostic patterns and failure modes for concurrent and async code — data races, deadlocks, atomicity, async/await pitfalls, and idempotency as the key design property.
related:
  - {slug: error-handling-and-resilience, rel: relates-to}
  - {slug: api-design, rel: see-also}
  - {slug: database-design-and-indexing, rel: see-also}
  - {slug: test-strategy-and-flakiness, rel: see-also}
created: 2026-06-21
---

# Concurrency and Asynchronous Programming Patterns

Concurrent and async code fails in ways that are non-deterministic, hard to reproduce, and often invisible until load or network latency expose them. Understanding the canonical failure modes — data races, deadlocks, atomicity violations, async pitfalls, and non-idempotent operations — and their corresponding patterns is the prerequisite for writing correct concurrent software in any language.

## Data Races

A data race occurs when two goroutines or threads access the same memory location concurrently and at least one access is a write, with no synchronization between them. The result is undefined behavior: crashes, memory corruption, and silent wrong results that surface non-deterministically under load.

**Detection**: Use language-level race detectors during development and CI. Go ships one built in (`go test -race`, `go run -race`, `go build -race`). C/C++ and Rust use ThreadSanitizer (`-fsanitize=thread`). Race detectors only find races that occur at runtime — pass realistic concurrency workloads to maximize coverage.

**Prevention**:
- Prefer message-passing over shared memory: channels (Go), queues (Python asyncio), actors. If data flows through explicit channels, ownership is clear and simultaneous writes are structurally prevented.
- When shared memory is unavoidable, protect every access (read and write) with the same lock, or use atomic primitives for single-word values.
- Immutable data structures eliminate races by design: share freely after construction.

## Deadlocks

A deadlock is a state where two or more threads are each waiting for a resource held by the other, so none can proceed. Coffman's four necessary conditions: mutual exclusion, hold-and-wait, no preemption, circular wait. Breaking any one condition prevents deadlock.

**Lock ordering** (break circular wait): define a global acquisition order for all locks and enforce it everywhere. If lock A is always acquired before lock B, a cycle is impossible.

**Timeouts on lock attempts** (break hold-and-wait indefinitely): use `tryLock(timeout)` semantics. On timeout, release all held locks and retry after a random backoff. This introduces livelock risk if the backoff is not randomized.

**Lock-free and wait-free structures**: compare-and-swap (CAS) loops replace mutex sections for single-variable updates. No lock means no deadlock from that code path.

**Thread-pool-induced deadlock**: a task that blocks waiting for another task's result, when both tasks compete for slots in the same bounded pool, can deadlock the pool. The fix is a separate pool for blocking tasks, or restructuring the dependency so the blocking call is always the leaf — the only resource a task needs is the thread it already holds.

## Atomicity and Invariants

Atomicity means a set of operations either all complete or none are visible — intermediate state is never exposed to other threads. A single 64-bit store may not be atomic on 32-bit hardware; a read-modify-write of a counter is never atomic without explicit primitives.

**Single-variable updates**: use atomic primitives (`sync/atomic`, `java.util.concurrent.atomic`, `std::atomic`). CAS (`compare_exchange`) reads the current value, computes the new value, and writes only if the current value is still what was read — retries loop on conflict.

**Multi-step invariants**: use transactions (database ACID, STM) or hold a lock across the entire group of operations. Never release a lock between steps of an invariant, or publish intermediate state.

**Memory ordering**: acquiring a lock implies an acquire fence; releasing it implies a release fence. For lock-free code, specify the minimum ordering (acquire/release vs. seq_cst) explicitly — relaxed reads can reorder past writes otherwise.

## Async/Await Pitfalls

Async/await is cooperative: a task yields at `await` points and the runtime schedules another task. If a task never yields, or yields into blocking work, the event loop stalls.

**Blocking the event loop**: calling synchronous blocking I/O (file read, DNS lookup, `sleep`) from an async function blocks the entire thread running the loop. Remedy: offload to a thread pool — `asyncio.run_in_executor` (Python), `tokio::task::spawn_blocking` (Rust), `WorkerPool` patterns generally. CPU-bound computation has the same effect.

**Unbounded concurrency**: spawning a task per item in an unbounded input overwhelms memory and downstream services. Use a semaphore or bounded channel as a concurrency limiter before spawning. In Python: `asyncio.Semaphore(N)`. In Rust/Tokio: `JoinSet` with bounded capacity or `FuturesUnordered` with a stream buffer.

**Async contagion**: once a function is async, every caller must also be async (or use a blocking bridge). This propagates up the call stack. Design the async boundary deliberately — keep sync interfaces at the edges if the context is mostly sync, or commit to async throughout for a service.

**Unhandled rejected promises/tasks**: runtime behavior varies and changes across versions; Node.js can
terminate on an unhandled rejection, Python may warn for unawaited coroutines or unobserved task
exceptions, and a dropped Rust future stops being polled. Treat every spawned task as owned: observe
its result through `.catch()`, `await`, a join handle, or an explicit supervisor.

## Idempotency

An operation is idempotent if applying it multiple times produces the same result as applying it once. This is the key design property for safe retries under partial failure: the caller cannot distinguish a timeout that happened before the write from one that happened after.

**Idempotency keys**: the caller generates a unique key (UUID) per logical operation and sends it with every attempt. The server stores key → result, and on a duplicate request returns the stored result without re-executing. Used by Stripe (payment intents), and all major API gateways. The key must be stored atomically with the state change.

**Database upserts and conditional writes**: use the engine's atomic primitive—PostgreSQL
`INSERT … ON CONFLICT`, MySQL `INSERT … ON DUPLICATE KEY UPDATE`, or a DynamoDB conditional
`PutItem`/transaction—with conditions that encode the desired invariant. They are not automatically
idempotent: update expressions, triggers, counters, and returned values still matter. MySQL
`REPLACE` is not a generic upsert; on a conflict it can delete the old row and insert a new one,
changing keys and firing delete/insert side effects.

**Conditional writes**: `UPDATE orders SET status='shipped' WHERE id=:id AND status='pending'` — only succeeds once; subsequent retries match zero rows and are safe. Check affected-row count to distinguish the first execution from a retry.

## Optimistic vs. Pessimistic Concurrency

**Pessimistic** (lock before reading): acquire a mutex or `SELECT … FOR UPDATE` before accessing the resource. Safe under high contention; serializes all access; risks deadlock and starvation.

**Optimistic** (read, compute, write-if-unchanged): read without a lock, compute the new state, then write conditionally on a version column or CAS. If the write fails (version changed), retry from read. Best for low-contention reads with infrequent conflicts; degrades under high contention as retries multiply.

**When to choose**: optimistic is the default for user-facing reads in web applications (contention is low). Pessimistic is correct for financial ledgers, inventory, or any high-contention write where retry storms would be worse than serialization latency.

## Thread Pool and Executor Sizing

- **CPU-bound work**: pool size ≈ `num_cpus`. Adding more threads than cores causes context-switch overhead without additional throughput.
- **I/O-bound work**: threads spend most time waiting; pool size can be much larger (commonly `num_cpus * 2` to `num_cpus * 10`, or tuned empirically to keep CPU busy without exhausting file descriptors or connection slots).
- **Never mix**: a single pool with both CPU-bound and I/O-bound tasks causes one workload to starve the other. Use separate pools with separate size policies.
- **Virtual threads / green threads** (Java 21+, Go goroutines): designed for I/O-bound work; do not help CPU-bound throughput, and CPU-bound tasks pinned to a carrier thread can reintroduce starvation.

> Source: https://go.dev/doc/articles/race_detector · https://dev.mysql.com/doc/refman/8.4/en/replace.html · reviewed 2026-07-23
