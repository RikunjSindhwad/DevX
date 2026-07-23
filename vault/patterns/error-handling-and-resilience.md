---
id: error-handling-and-resilience
title: Error Handling and Resilience Patterns
type: pattern
tags: [resilience, error-handling, retry, backoff, circuit-breaker, timeout, bulkhead, graceful-degradation, distributed-systems]
summary: How to model errors, implement retries with backoff-and-jitter, set timeouts, use circuit breakers and bulkheads, and degrade gracefully — the canonical toolkit for resilient services.
related:
  - {slug: api-design, rel: relates-to}
  - {slug: database-design-and-indexing, rel: see-also}
  - {slug: observability-and-logging, rel: see-also}
created: 2026-06-21
---

# Error Handling and Resilience Patterns

In any distributed system, remote calls fail — servers go down, networks blip, upstream services hit capacity. The question is not whether failures occur but whether they cascade. This entry covers the six-pattern toolkit (error modeling, retries, backoff + jitter, timeouts, circuit breakers, bulkheads) plus graceful degradation as the fallback layer. Used together they convert outright failures into bounded, self-healing degradation.

## Error Modeling

Classify every error before deciding how to respond:

| Class | Examples | Action |
|---|---|---|
| Transient | network timeout, 503 Service Unavailable, 429 Too Many Requests | retry with backoff |
| Permanent for the same request | most 400/401/403/422 responses | fail fast or correct credentials/payload |
| Ambiguous | timeout after a non-idempotent write | retry only if idempotent; otherwise surface to caller |

Surface retryability explicitly through a typed error, protocol contract, or `Retry-After`. HTTP status
families are only a starting point: some 5xx failures are deterministic, while 408, 409, 425, 429, and
eventual-consistency 404 responses may be retryable under a documented contract. Do not infer policy
from "4xx versus 5xx" alone.

**Never retry a permanent error.** Retrying a 400 wastes resources and adds load to a backend that is already telling you the request is wrong.

## Retries

Retries are "selfish": each retry consumes more server capacity in exchange for a higher chance of client success. This trade-off is worth making for rare or transient failures; it becomes destructive under sustained overload (AWS Builders' Library).

Rules before retrying:

1. **Idempotency first.** Retry only operations whose defined effect is safe to repeat. HTTP
   `GET`/`HEAD` are specified as safe and idempotent, but a bespoke "read" may consume a cursor, mark a
   message read, or trigger other state. Writes need explicit idempotency keys or conditions (for
   example, a client-generated `Idempotency-Key` or conditional `PUT` with an ETag). A timeout does not
   mean the write did not happen.
2. **Bound attempts by deadline and budget.** Use a small finite starting policy, then tune from latency,
   success-rate, and overload data. Unlimited retries delay recovery and amplify backend load.
3. **Retry at one layer.** In a five-deep call stack, three retries at each layer multiplies load by 3^5 = 243× on the bottom dependency. Retry at the entry point or at a single designated layer; lower layers propagate the error upward instead.
4. **Retry budgets at the fleet level.** Use a token bucket to cap the fleet-wide retry rate. AWS SDKs (since 2016) implement this: once the bucket is exhausted, retries are rejected locally without ever hitting the network (AWS Builders' Library). Google's adaptive throttling achieves the same effect: each client self-regulates when `requests ≥ K × accepts` (Google SRE Book, Ch. 21, default K=2).

## Exponential Backoff + Jitter

Capped exponential backoff alone is insufficient: all clients back off to the same ceiling and then retry simultaneously, producing contention spikes. Jitter breaks the correlation.

**Formula — full jitter (preferred):**

```
sleep = random_between(0, min(cap, base * 2 ** attempt))
```

- `base`: initial backoff (e.g., 100 ms)
- `cap`: maximum backoff (e.g., 30 s)
- `attempt`: zero-indexed retry count

Full jitter draws from the full range `[0, capped_backoff]`, giving the most even spread of retries across time. AWS's 2015 simulation showed that full jitter cuts client work by more than half compared to un-jittered exponential backoff and reduces time-to-completion, while equal jitter (keeping half the base) prevents very short sleeps at the cost of slightly less spread (AWS Architecture Blog, Marc Brooker, 2015).

**Why jitter matters:** Without jitter, N clients that all fail at the same moment all retry at the same moment (thundering herd). Jitter spreads arrivals across the backoff window, converting a spike into an approximately constant arrival rate. The same principle applies to all periodic work (cron jobs, cache refreshes): jitter the schedule so a fleet of hosts does not all fire at second 0 of every minute.

**Equal jitter alternative:**

```
v = min(cap, base * 2 ** attempt)
sleep = v/2 + random_between(0, v/2)
```

Use equal jitter when a minimum wait between retries matters (e.g., rate-limited APIs with a fixed `Retry-After` floor).

## Timeouts

Set a timeout on every network call without exception — this is the most basic form of fault isolation (AWS Builders' Library). Two distinct timeouts apply to most connections:

- **Connect timeout**: how long to wait for the TCP + TLS handshake (typically 1–5 s; shorter than request timeout because a failed handshake is unambiguous).
- **Read/request timeout**: how long to wait for the full response after connection is established.

**Choosing timeout values:** Start from the downstream service's latency distribution. Pick the percentile corresponding to your acceptable false-timeout rate (e.g., p99.9 for 0.1% false timeouts). Add network latency headroom for cross-region or internet calls. Avoid setting timeouts from p50 when p99 is much higher — a small latency increase will then cause all requests to time out.

**Propagate deadlines.** Pass an end-to-end deadline in every RPC context (e.g., `context.WithDeadline` in Go, gRPC deadline propagation). Each hop deducts its expected processing time from the remaining budget before passing the shorter deadline downstream. This prevents a slow leaf service from holding resources all the way up the call tree past the point where the original caller has already given up.

**Timeout < retry window.** The per-attempt timeout must be shorter than the total retry budget, otherwise the first attempt always exhausts the budget and retries never run.

**Pitfall — incomplete coverage.** Timeouts that do not cover DNS resolution or TLS renegotiation can still hang. Prefer well-tested HTTP clients that apply the timeout to the full request lifecycle rather than rolling socket-level timeouts manually (AWS Builders' Library, TLS connection case study).

## Circuit Breaker

A circuit breaker wraps a downstream call and monitors failure rate. When failures exceed a threshold, it "trips" and all further calls fail immediately without touching the downstream — preventing cascade failures and giving the downstream time to recover. Pattern first described by Michael Nygard in *Release It!*; popularized by Martin Fowler (2014).

**Three states:**

```
CLOSED  ──[failures ≥ threshold]──►  OPEN  ──[timeout expires]──►  HALF-OPEN
  ▲                                                                      │
  └──────────────────[trial call succeeds]──────────────────────────────┘
```

| State | Behavior |
|---|---|
| **Closed** | Requests pass through; failure count increments on error; success resets count |
| **Open** | All requests fail immediately with `CircuitBreaker::Open`; no downstream calls made |
| **Half-Open** | One (or a limited number of) trial request(s) pass through; success → Closed; failure → Open again |

**Configuring thresholds:** Trip on N consecutive failures, or on an error rate exceeding X% over a sliding window. The sliding-window approach is less sensitive to bursts; the consecutive-count approach is simpler to reason about. Azure Architecture Center recommends combining both: error count within a time window.

**Why it prevents cascades:** Without a circuit breaker, a slow downstream causes all callers to accumulate in-flight requests blocked on timeouts, exhausting thread pools and connection pools (shared resources), which then causes the calling service to fail for unrelated downstream calls (resource starvation cascade). The circuit breaker redirects callers to a fast failure path, shedding load before the caller's own resources are exhausted.

**Circuit breaker + retry interact:** Retry logic must recognize `CircuitBreaker::Open` as a non-retryable error, not a transient failure. Retrying an open circuit re-submits requests that the breaker has already determined will fail, defeating its purpose (Azure Architecture Center).

## Bulkhead

Borrowed from ship hull design: divide the hull into watertight compartments so flooding one compartment does not sink the ship.

In services, a bulkhead isolates resource pools per downstream dependency:

- Separate **thread pools** per downstream (so a slow dependency does not consume the shared worker pool).
- Separate **connection pools** per downstream.
- **Semaphore-based** bulkheads: limit the number of concurrent in-flight calls to a single downstream.

Without bulkheads, a single slow or failing downstream can exhaust the shared resource pool, causing the calling service to fail for all downstreams — including healthy ones. The [[problem-solving-techniques]] entry notes: "a connection pool, and a semaphore are the same resource-budget pattern."

**Sizing bulkheads:** Start from expected concurrency per downstream at peak load with some headroom (e.g., 2×). Too small and you artificially cap throughput; too large and you lose isolation. Monitor active/waiting counts and alarm when the waiting queue is non-zero for more than a few seconds.

Bulkhead failure mode: when the pool is full, new requests fail fast with a `BulkheadFullException` or equivalent. This is the intended behavior — fail the caller quickly rather than queuing indefinitely and propagating the slowness upstream.

## Graceful Degradation

When a dependency is unavailable, return a degraded-but-useful response rather than a hard failure.

**Degraded-mode options (ordered by decreasing freshness):**

1. **Stale cache hit** — return the last known good response (with a `Warning: 110` header or equivalent if freshness matters to clients).
2. **Partial response** — omit the section backed by the failing dependency; return the rest.
3. **Static fallback** — a default value, a locally computed approximation, or a feature-flag-off path.
4. **Feature flag off** — disable the feature entirely for the duration of the outage.
5. **Serve error** — last resort; used when none of the above is acceptable (e.g., payment processing where a stale price is worse than no price).

Google SRE Book (Ch. 21) describes this as "serve degraded results when necessary, handle resource errors transparently when all else fails."

**Fail open vs fail closed:**

| Decision | Fail Open | Fail Closed |
|---|---|---|
| Definition | Allow access / return default when dependency is unreachable | Deny access / return error when dependency is unreachable |
| Use when | Availability > correctness (e.g., product recommendations, analytics) | Correctness > availability (e.g., authorization checks, fraud detection) |
| Risk | May serve stale or permissive data | May refuse legitimate requests during outages |

Define the degraded-mode behavior explicitly before the outage — not during it. Write it into runbooks and feature-flag configurations so on-call engineers have a playbook rather than an improvised decision under pressure.

## Putting It Together

These patterns layer:

```
Request
  │
  ├─[bulkhead: pool not exhausted?]──NO──► fail fast
  │
  ├─[circuit breaker: OPEN?]────────YES──► fail fast (or degraded response)
  │
  ├─[timeout: deadline propagated]
  │
  ├─[attempt]──FAIL (transient)──► retry with exponential backoff + jitter
  │                                 (up to budget; check idempotency)
  │
  └─[degraded mode: dependency down?]──► stale cache / partial / feature off
```

Layer order matters: apply the bulkhead and circuit breaker before issuing a request (cheap, synchronous decisions); apply timeouts per attempt; apply retries across attempts; apply degraded mode at the response level.

**Observability tie-in.** None of these patterns work well without metrics. Instrument: circuit breaker state transitions, bulkhead rejection rate, retry rate per downstream, timeout rate per endpoint. Alert on sustained retry rate elevation (leading indicator of overload) and circuit breaker opening (lagging indicator of dependency failure). See [[observability-and-logging]] for the instrumentation pattern.

> Source: https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ · promoted by /devx:devx-vault · 2026-06-21
