---
id: ci-cd-and-deployment
title: CI/CD & Deployment Strategies
type: ops
tags: [ci, cd, continuous-integration, continuous-delivery, deployment, blue-green, canary, rolling, pipeline, observability]
summary: Core principles and trade-offs for continuous integration pipelines, delivery vs. deployment distinctions, deployment strategies (blue-green, canary, rolling), environment parity, and observability for safe releases.
related:
  - {slug: owasp-top-10-quickref, rel: relates-to}
  - {slug: test-strategy-and-flakiness, rel: relates-to}
created: 2026-06-20
---

# CI/CD & Deployment Strategies

Continuous integration and delivery practices collapse the feedback loop between writing code and running it in production. The shorter that loop, the cheaper each mistake is to catch and fix. These practices are not tool choices — they are commitments to a way of working that shapes how a team writes code, manages branches, and ships software.

## Continuous Integration

CI means every developer integrates their work into the shared mainline at least once a day. The discipline rests on three pillars:

- **Trunk-based development.** Short-lived branches (hours, not days) merged into a single main line. Long-lived feature branches defer integration pain and create merge "big bangs." Feature flags let incomplete work ship in a dormant state rather than in a parallel branch.
- **Fast, reliable automated builds.** Every push triggers a build-and-test run. The pipeline must be fast enough that developers wait for it rather than skip it — aim for a ten-minute ceiling on core feedback. Slow pipelines get bypassed.
- **Fail-fast, fix-first culture.** A broken build is the team's top priority. A green mainline is a shared social contract; leaving it red is equivalent to blocking everyone's work.

A well-designed pipeline gates on, in order of speed: static analysis and linting → unit tests → integration tests → security scans (see [[owasp-top-10-quickref]]) → artifact build. Anything that cannot run in the pipeline's time budget is promoted to a separate asynchronous stage, never removed.

The test suite that CI exercises must itself be stable — flaky tests erode trust in the signal. See [[test-strategy-and-flakiness]] for managing flakiness without disabling tests.

## Continuous Delivery vs. Continuous Deployment

These terms are often conflated but describe different commitments:

- **Continuous delivery** means the mainline is *always* in a releasable state. Deploying to production is a deliberate, low-ceremony human decision — the pipeline proves the build is safe; the team decides when to pull the trigger.
- **Continuous deployment** removes the human gate entirely: every green build that passes all pipeline stages is automatically promoted to production.

Continuous delivery is the prerequisite; continuous deployment is an optional further step. Teams with regulatory constraints, staged customer rollouts, or coordinated release trains often stop at delivery intentionally.

## Deployment Strategies

Choosing how to move a new version into production is a risk-management decision. The right choice depends on blast radius tolerance, traffic volume, and rollback requirements.

### Blue-Green Deployment

Maintain two identical production environments, "blue" (live) and "green" (staging). Deploy the new version to the idle environment, run smoke tests, then switch the router (load balancer, DNS, service mesh) to cut over traffic atomically. Rollback is an instant router flip back.

Trade-offs: requires double the production infrastructure for the brief cutover window; database migrations must be backward-compatible with both versions simultaneously (expand-then-contract pattern); session state must either be externalized or drained before cutover.

### Canary Releases

Route a small percentage of real traffic (e.g., 1–5%) to the new version while the majority stays on the old. Monitor error rates, latency, and business metrics. Gradually increase the canary slice if metrics hold, abort and re-route if they degrade.

Trade-offs: exposes a real user subset to potential defects (mitigate by choosing a non-critical cohort first); requires instrumentation and automated traffic-shifting capable of fine-grained percentages; rollback is fast (re-route the slice) but a bad canary can still impact live users before alerting fires.

### Rolling Deployment

Replace instances of the old version one at a time (or in small batches), with health checks gating each step. The cluster runs mixed versions during the roll.

Trade-offs: no extra infrastructure cost; rollback requires a reverse roll (not instantaneous); API and database schema changes must be compatible across both the old and new version simultaneously throughout the roll. Good fit for stateless services; risky for stateful ones without care.

### Choosing Among Them

| Strategy | Rollback speed | Infra cost | Mixed-version window |
|---|---|---|---|
| Blue-green | Instant (router flip) | High (2× capacity) | None — atomic cutover |
| Canary | Fast (re-route slice) | Low (small canary pool) | Extended, controlled fraction |
| Rolling | Slow (reverse roll) | None | Extended, whole cluster |

No strategy eliminates risk; each shifts it. Blue-green minimizes user impact but requires infrastructure. Canary catches defects with minimal blast radius but demands mature observability. Rolling is cheap but demands careful API versioning.

## Build Artifacts and Environment Parity

A build artifact (container image, compiled binary, versioned package) must be built once and promoted through environments unchanged. Rebuilding from source per environment risks introducing variance — "it worked in staging" bugs trace back here.

Configuration that differs between environments (credentials, endpoint URLs, feature flags, replica counts) belongs in the environment, not baked into the artifact. The Twelve-Factor methodology codifies this as "store config in the environment": all config is injected at runtime via environment variables or a secrets manager, never committed to source. The artifact becomes an immutable unit of deployment; what changes between dev, staging, and production is purely config.

## Observability for Safe Deploys

A deployment is not done when the rollout completes — it is done when the metrics confirm the system is healthy under real load. Safe deploys require:

- **Structured logs** that expose errors, latency, and business events, queryable by version and cohort.
- **Metrics and dashboards** with pre-drawn views for the KPIs that matter for this service — error rate, p99 latency, throughput, queue depth. Alert thresholds should be set before deploy, not after incidents.
- **Distributed traces** for services with non-trivial call graphs: a canary with a latency regression in a downstream RPC won't surface in top-level error rates alone.
- **Health checks** that the orchestrator can act on — readiness probes (is this instance ready to receive traffic?) and liveness probes (is this instance still alive?) let the platform automate recovery without human paging.

Release engineering at scale formalizes this into a release pipeline where each stage's promotion gate is an automated policy check, not a manual sign-off (the Google SRE model calls this "policy-enforced" release engineering). The human judgment is encoded into the policy; the rollout executes it consistently.

> Source: https://martinfowler.com/articles/continuousIntegration.html · curated · 2026-06-20
