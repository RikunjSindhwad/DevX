---
id: dependency-injection
title: Dependency Injection & Seams for Testability
type: pattern
tags: [dependency-injection, testability, design]
summary: How to pass collaborators through narrow seams so modules stay easy to test and change.
related:
  - {slug: test-first-tdd, rel: see-also}
created: 2026-06-20
---

# Dependency Injection & Seams for Testability

A design pattern entry. Goal: make modules easy to change and easy to test.

## The idea
Pass collaborators in (constructor/params) instead of constructing them inside. The unit under test gets test doubles; production gets real implementations. The "seam" is where you substitute.

## Smells that call for DI
- A function that opens its own DB connection, reads the clock, or calls the network — untestable without that resource.
- `import requests` used deep inside business logic.
- Singletons/global state read directly.

## Lightweight DI by language (no framework needed)
- **Python**: default arguments / a small `Protocol` + pass the dependency; or a tiny factory. Avoid heavyweight containers for small apps.
- **TypeScript**: constructor injection; an interface for the collaborator. Reserve frameworks (Nest/InversifyJS) for large apps.
- **Go**: accept interfaces, return structs; wire in `main`.

## Keep it modular
- Depend on narrow interfaces, not concretions.
- Wire dependencies at the edge (composition root / `main`), not scattered through the code.
- One reason to change per module (single responsibility) keeps the graph shallow.

> Source: https://martinfowler.com/articles/injection.html · curated · 2026-06-20
