---
id: python-package-selection
title: Choosing Python Packages (Selection Guidance)
type: package
tags: [python, packages, dependencies, selection]
summary: Criteria for selecting Python dependencies with maintenance, fit, footprint, license, and version policy in mind.
related:
  - {slug: dependency-injection, rel: see-also}
created: 2026-06-20
---

# Choosing Python Packages (Selection Guidance)

Used by the designer when picking dependencies. At decision time, verify the release and supported
Python versions from the package's official index metadata, documentation, changelog, source, and
advisory databases. Choose a version policy that matches the artifact: reproducible lockfiles for
applications/tools and tested compatibility bounds for published libraries.

## Selection criteria (record evidence before adding a dependency)
- **Maintenance/governance**: release cadence appropriate to the project's maturity, supported Python
  versions, issue/security response, multiple maintainers or a credible stewardship plan. A stable
  library may not need a release every six months.
- **Adoption evidence**: relevant production usage and ecosystem integration can reduce uncertainty,
  but downloads and stars are noisy and are not quality or security scores.
- **Fit**: solves the actual problem without dragging a framework you don't want.
- **Footprint/supply chain**: transitive dependency count, build backend, binary wheels/platform support,
  install-time code, provenance/signing where available, and current advisories (`pip-audit`/OSV).
- **License**: compatible with the project and its distribution model.
- **Exit cost**: API surface you depend on, data-format lock-in, and the effort to replace it.

## Candidate categories (research current options)

Start from the project's existing stack. If a capability is missing, compare maintained candidates for
the required web style, sync/async HTTP behavior, validation model, package management, lint/type/test
workflow, database/driver, operating systems, and supported Python versions. Named package choices age
quickly; record why the selected version fits this project and the evidence date.

## Anti-patterns
- Adding a dependency for a 10-line utility.
- Unpinned application/tool dependencies that let a transitive bump break the build.
- Exact pins in published libraries when they unnecessarily constrain downstream consumers.
- Picking the first search result without checking maintenance.

> Source: https://packaging.python.org/en/latest/discussions/install-requires-vs-requirements/ · https://pip-audit.readthedocs.io/ · reviewed 2026-07-23
