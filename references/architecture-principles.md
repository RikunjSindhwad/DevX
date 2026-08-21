# Architecture Principles

What "modular and easy to change" means in practice. The designer applies these (architect mode); the
reviewer checks structural changes against them.

## Design for change, not for prophecy
- Build the **smallest structure that meets the current need**. YAGNI: no speculative layers,
  frameworks, or abstractions for futures that may never arrive.
- Optimize for the change you'll actually make next, not a hypothetical one.

## Vertical slices + explicit integration
- Prefer **thin vertical slices**: each phase is a runnable increment that exercises the stack
  end-to-end, over a horizontal "build all modules, then assemble" sequence.
- When components are genuinely built separately, include an explicit **integration/assembly phase**
  whose acceptance criteria are end-to-end — assembly is never left implicit.
- This is not a mandate for strict bottom-up ordering; it favors runnable increments and a real
  integration phase, not a fixed build order.

## Product GUI baseline comes early
- For product-facing web/desktop apps, the roadmap must deliver a **minimum visually satisfactory,
  usable shell or first vertical slice early**: navigation/header or app frame, primary screen layout,
  empty/error/busy states, realistic/demo data where appropriate, and enough styling that the operator
  can judge the product direction.
- Gate this early slice with the operator before accumulating many backend or feature phases, unless a
  security/data foundation is truly required first. Even then, the first visible phase after the
  foundation must establish the visual baseline rather than leaving "make it look good" to the end.
- Later phases extend the baseline; they do not introduce unrelated visual languages or defer global
  shell/design-system work as an unowned backlog item.
- A new/replaced visual language records one `Product Interface Direction` in `.devx/architecture.md`;
  localized changes inherit it. Canonical criteria live in `references/ui-design.md`.

## Boundaries & dependencies
- Split by **responsibility/domain**, not by technical layer alone. One reason to change per module.
- **Narrow interfaces** between modules; hide internals. Callers depend on the contract, not the guts.
- **Dependencies point inward**: domain/core logic doesn't import infrastructure (DB, HTTP, framework).
  Infrastructure depends on the core, not vice versa.
- **Wire at the edge**: construct concrete dependencies in a composition root (`main`/entrypoint), not
  scattered through the code (see `vault/patterns/dependency-injection.md`).

## Testability is a design property
- If it's hard to test, the design is telling you something. Add a seam (inject the collaborator)
  rather than reaching for heavy mocking.
- Keep side effects (I/O, network, clock) at the edges so the core is pure and unit-testable.

## Explicit over implicit
- Make data flow and control flow obvious. Prefer explicit parameters to hidden globals/singletons.
- Errors are part of the interface — design how failures propagate.

## Boring, maintained, pinned
- Prefer well-maintained, widely-used technology over novelty. Justify anything exotic.
- Pin dependency versions; treat a dependency as a long-term liability, not a free win.

## Centralize domain policy & reference data
- Policy and reference data — allowlists, weights, thresholds, **display labels** — live in **one**
  config/policy layer, separate from engine logic. A second copy drifts: an item scored "official" by
  one map and labeled "unofficial" by another is a user-visible bug.
- UI labels and the logic that uses them read from the **same source**.
- Separate calibration/policy from code; document the calibration dataset; require representative
  fixtures before tuned weights are treated as product logic.

## Shared constants & design tokens, one home
- Reusable presentational/config values — colors, spacing, sizes, timeouts, repeated literals,
  policy/domain maps — live in a **single** tokens/constants module and are **referenced, never
  re-typed**. A literal appearing in ≥2 places is extracted.
- No unexplained magic literals; a repeated literal is a review finding.
- Tokens or maps referenced nowhere are dead — removed, not kept "just in case".

## Model the domain accurately; localize at the edge
- Domain models reflect real platform/domain semantics — don't conflate distinct concepts (e.g.
  *declared* vs *granted*, model vs runtime state). When the model encodes platform behavior, **verify
  it against the real platform** (a research trigger), don't guess from memory.
- Parsing/domain layers emit **codes/facts**; **all** user-facing text — labels, buttons, tooltips,
  errors, empty states, status messages, settings, risk/domain labels — lives in i18n catalogs or an
  external messages module, not just parser output, and never hardcoded in logic (mirrors the code
  standard on externalized user-facing strings).

## Stateful & GUI apps carry an explicit lifecycle
- A UI or long-running app has an explicit **state machine** (idle / working / done / error). Background
  work is **guarded** (no duplicate starts), **cancellable**, and **cleaned up**; slow I/O runs **off**
  the UI thread. The top-level widget delegates to a **presenter/controller** once it coordinates
  workflows, background work, I/O, and navigation — don't let one widget own everything.
- Build mechanics (worker lifecycle, off-thread export, progress/cancel): `tools-guide/native/gui-desktop.md`.

## Keep the living doc honest
- `.devx/architecture.md` must match reality. When structure changes, the doc changes in the same
  workstream (docs agent). A drifted architecture doc is worse than none.
