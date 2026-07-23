---
id: observability-and-logging
title: Observability and Structured Logging
type: pattern
tags: [observability, logging, metrics, tracing, opentelemetry, correlation-id, structured-logs, monitoring, sre]
summary: Choosing useful telemetry signals, structured logging practices, correlation IDs, log levels, sensitive-data controls, and OpenTelemetry with per-language maturity checks.
related:
  - {slug: api-design, rel: relates-to}
  - {slug: ci-cd-and-deployment, rel: relates-to}
  - {slug: error-handling-and-resilience, rel: see-also}
  - {slug: auth-and-secrets, rel: see-also}
created: 2026-06-21
---

# Observability and Structured Logging

Observability is the ability to understand a system's internal state from its outputs. Logs, metrics,
and traces are complementary, but no fixed checklist guarantees complete observability. Instrument the
signals that answer the service's operational questions and SLOs; add baggage only for carefully
controlled cross-cutting context.

## Complementary signals

**Logs** are the stream of discrete, time-ordered events emitted by a running process. They answer "what happened?" at a specific moment. A twelve-factor application writes its event stream unbuffered to stdout and lets the execution environment handle routing and storage — the app must not manage log files itself (12factor.net/logs).

**Metrics** are numeric measurements aggregated over time. They answer "how is the system behaving right now and over the past N minutes?" They are cheap to store and fast to query, making them the right layer for dashboards and alerting.

**Traces** are request-scoped records of work that span components. Parent/child span relationships
form a hierarchy, while span links can express additional causal relationships. Each span captures one
unit of work (an HTTP call, a database query, a queue consumer step) with timing and attributes. Traces
help answer "why did this request take so long, and where did it spend its time?"

OpenTelemetry documents traces, metrics, logs, and baggage. Events and profiles have separate,
evolving support. Signal and feature maturity varies by language, so check the current per-language
status before promising a uniform implementation.

## Structured Logging

**Emit structured fields in production.** JSON is a common transport, but native structured-event APIs
and platform formats are also valid. Avoid free-form concatenation that requires fragile regex parsing;
define a versioned field contract and configure the chosen backend's parsing/indexing deliberately.

An illustrative service-event field set:

```json
{
  "timestamp": "2026-06-21T14:32:01.452Z",
  "level": "INFO",
  "service": "checkout-api",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "request_id": "req_abc123",
  "message": "Order placed successfully",
  "order_id": "ord_789"
}
```

Use an unambiguous timestamp and standardize field semantics across producers that must be queried
together. Choose nesting and cardinality for the selected logging backend; validate the schema and
query-cost implications rather than applying a universal depth rule.

## Log Levels

Four common levels cover many production cases; map framework-specific `TRACE`, `FATAL`, audit, or
security events deliberately rather than forcing every signal into this table:

| Level | Meaning | Action |
|---|---|---|
| ERROR | An operation failed or could not satisfy its contract | Alert only when the service's policy makes it actionable |
| WARN | Degraded or unexpected operation that completed or recovered | Monitor; may escalate |
| INFO | Normal lifecycle or business events selected by policy | Usually no immediate action |
| DEBUG | Diagnostic detail | Enable only where its volume and data exposure are acceptable |

**Avoid log-level inflation.** Logging every handled exception at ERROR creates alert fatigue and buries
real failures. Classify recovered retries and request-validation failures according to the service's
error contract and alert policy; do not equate every ERROR record with an automatic page.

Choose the production threshold from volume, cost, and incident needs. If runtime DEBUG toggling is
supported, protect and audit the control plane, scope it narrowly, and expire the change.

## Correlation IDs

A correlation ID (also called request ID in many systems) is an identifier propagated across the
components participating in an operation. It complements, but is not necessarily interchangeable with,
a trace ID.

Rules for correlation IDs:

1. **Generate at the entry point.** The API gateway or first service generates the ID. If a client
   supplies `X-Request-ID`, bound its length/character set and decide whether to replace it with an
   internal ID while retaining a separately labeled external correlation value.
2. **Propagate on every outbound call.** Pass it as an HTTP header (`traceparent` per W3C TraceContext, or `X-Request-ID` for simpler setups) on every downstream HTTP call, message queue publish, and RPC.
3. **Include it in every log line.** Inject it into the logging context (MDC in Java, contextvars in Python, AsyncLocalStorage in Node.js) so all log statements in a request's call stack include it automatically.
4. **Return it to the caller.** Echo it in the response as `X-Request-ID` so clients can reference it in support tickets.

With consistent trace context in logs and telemetry, operators can correlate a request across services;
query speed and completeness depend on sampling, propagation, ingestion, retention, and backend design.

## What NOT to Log

**Never write the following to logs under any circumstances:**

- Passwords and passphrases
- Session tokens, access tokens, refresh tokens, API keys
- Full credit card numbers (PCI DSS violation)
- Social Security / national ID numbers
- Protected Health Information (HIPAA scope)
- Private encryption keys or certificates
- Database connection strings with credentials embedded
- Full request/response bodies when they may contain any of the above

The OWASP Logging Cheat Sheet defines this as a categorical rule: sensitive data of higher security classification than the logging system is authorized to store must never appear in log records.

The correct approach is to **omit, redact, or deliberately pseudonymize before logging**. A plain hash
of low-entropy personal data may be reversible by enumeration and can remain regulated personal data.
Log a non-sensitive internal reference, not an email address; log only a permitted display fragment,
not a full payment identifier. Build automated pipeline-level filters that redact known-sensitive
fields, and verify them with tests; do not rely only on call-site discipline. See [[auth-and-secrets]]
for complementary secrets practices.

## Metrics

Three instrument types cover the majority of production use cases:

- **Counter** — monotonically increasing within an instrument/process lifetime. Examples:
  `http_requests_total`, `errors_total`, `cache_hits_total`. Backends must handle process restarts/resets
  when computing rates.
- **Gauge** — current value, can go up or down. Examples: `queue_depth`, `active_connections`, `memory_used_bytes`.
- **Histogram** — distributes observations into configurable buckets; compute percentiles. Examples: `http_request_duration_seconds`, `db_query_latency_ms`.

The **USE method** (Utilization, Saturation, Errors) applies across every resource in the system: for each resource (CPU, memory, network, disk, thread pool), measure how utilized it is, how saturated (queued/waiting), and the error rate. This gives a systematic coverage checklist.

The **Four Golden Signals** from Google SRE Chapter 6 are a useful starting lens for many
request-serving systems:

1. **Latency** — time to service a request; track successful and failed requests separately
2. **Traffic** — requests per second (or relevant throughput unit)
3. **Errors** — rate of failed requests (explicit 5xx, implicit wrong content, policy violations)
4. **Saturation** — how full the most-constrained resource is; latency at p99 is often the leading indicator

Adapt them to the service's user journeys, SLOs, queues, batch work, and business failure modes.

## Distributed Tracing

A **span** is the atomic unit: it records a named operation, its start time, its duration, its status, and key-value attributes. Spans link to a parent span via a parent span ID, forming a tree. The root span of a tree is the entry-point request; every downstream call is a child or descendant span.

**W3C TraceContext** defines the `traceparent` HTTP header format:
`{version}-{trace-id}-{parent-span-id}-{trace-flags}`. The trace ID remains stable across a trace while
the parent span ID changes across hops. OpenTelemetry instrumentation reads and writes this header when
the W3C TraceContext propagator and relevant client/server instrumentation are configured; adding an
SDK alone does not guarantee propagation.

**Sampling** controls cost. Full sampling can be useful in small development/staging environments, but
high-volume load tests may also require sampling:

- **Head-based sampling** — the decision is made at the root span (e.g., 5% of all requests). Simple and low overhead; loses detail for rare errors that weren't sampled.
- **Tail-based sampling** — the decision is deferred until the full trace is complete (e.g., sample 100% of traces containing an ERROR span). Higher fidelity for error investigation; requires a stateful Collector component (the OpenTelemetry Collector supports tail sampling via the `tailsampling` processor).

Choose sampling from traffic volume, telemetry budget, privacy, and diagnostic goals. Tail policies can
prefer errors and SLO outliers, but capacity-plan the Collector and understand that "always keep" is
still constrained by dropped data and pipeline limits.

## OpenTelemetry as the Unification Layer

OpenTelemetry (OTel) is the CNCF standard for observability instrumentation. It provides:

- **APIs and SDKs** across many languages; signal stability and feature completeness differ, so consult
  the current language status matrix.
- **The OpenTelemetry Protocol (OTLP)** — a common transport for supported telemetry signals.
- **The OTel Collector** — a vendor-neutral agent/gateway that receives telemetry, processes it (batching, filtering, attribute enrichment, tail sampling), and exports to any backend.

Instrumenting against OTel reduces backend coupling, but exporters, semantic conventions, sampling, and
backend capabilities still require configuration and sometimes code changes.

Log/trace correlation requires a compatible logging bridge or instrumentation that injects active
`trace_id`/`span_id`, plus backend support; do not assume every SDK/logger combination does this
automatically.

> Source: https://opentelemetry.io/docs/concepts/signals/ · https://opentelemetry.io/docs/languages/ · reviewed 2026-07-23
