# Product Interface Design Contract

Load this reference only when work creates or changes a product-facing web, desktop, or mobile interface.
It makes visual quality explicit without imposing a framework, fashionable style catalogue, design score,
or new agent.

## 1 — Inherit before inventing

First identify the visual authority, in order: supplied design/brand guidance → existing tokens and shared
components → representative accepted screens and `.devx/ui-gallery/` → current product conventions. A
localized change **inherits** that world. It must not introduce a new type scale, radius family, shadow,
accent palette, layout grammar, or component variant without an approved reason.

A new UI or intentional replacement of the visual language requires the architect pass and a durable
`## Product Interface Direction` in `.devx/architecture.md`. Use the existing Stage 01 architecture gate;
do not add another operator gate.

## 2 — Product Interface Direction

The designer records one recommended direction—not a menu of aesthetics—with:

- **surface job:** persuade, operate, read, or experience;
- **audience and primary task:** usage environment, frequency, density, device/input constraints;
- **authority to inherit:** token/component/brand/reference paths and representative screens;
- **visual thesis:** one sentence describing the intended character, plus one purposeful differentiator;
- **anti-references:** specific generic/inappropriate patterns this product must avoid;
- **typography:** roles and scale for display/heading/body/label/data, including long/localized text;
- **semantic color:** background/surface/text/action/status roles and verified foreground/background pairs;
- **composition:** grid, spacing rhythm, density, radius, elevation, icon and imagery language;
- **states:** default, hover, focus, active, disabled, loading, empty, error, success;
- **responsive rules:** what reflows, stacks, collapses, scrolls, or remains fixed at desktop/mobile;
- **motion:** purpose, duration character, interruption, and reduced-motion equivalent;
- **signature detail:** at most one memorable element that supports the surface job;
- **references/assets:** URLs or paths, usage/license status, dimensions/aspect ratio, alt behavior, and
  generation provenance where applicable.

Operational dashboards may deliberately use a system/workhorse font and dense layout. Distinctive never
overrides readability, performance, localization, accessibility, or platform consistency.

## 3 — Phase-plan visual acceptance

Every UI phase points to the approved/inherited Product Interface Direction and names:

- exact changed views and states;
- token/component owners to reuse;
- desktop and mobile composition expectations;
- typography and primary/secondary action hierarchy;
- long text, localization, zoom/text scaling, and overflow behavior;
- focus/keyboard/touch behavior and theme variants when applicable;
- asset source/provenance and layout-shift dimensions;
- motion purpose and reduced-motion outcome;
- sanitized gallery shots expected from verification.

Words such as "modern", "beautiful", "clean", or "polished" are not acceptance criteria. State the
observable hierarchy, composition, token, state, or behavior that would make the claim true.

## 4 — Browser/design verification

The existing `devx:ui:browser` agent performs both functional and design-quality verification:

1. Read the direction and phase criteria. Extract incumbent tokens/shared components and one or two
   representative accepted screens before judging a new render.
2. Capture a bounded batch: 1440px desktop, 375px mobile, any operator-named viewport, and only the key
   changed states. Desktop GUI uses the equivalent standard + cramped sizes.
3. Inspect computed/rendered values—not source declarations alone—for headings, controls, panels, fields,
   spacing, colors, radius, shadows, overflow, focus, and disabled states.
4. Compare against the approved/inherited direction, current tokens, prior accepted gallery, and an
   approved comp/reference only when one genuinely exists.
5. Report hierarchy/primary action, typography, color/contrast, spacing/rhythm, component consistency,
   task-appropriate density, imagery/icon coherence, responsive recomposition, state completeness,
   accessibility, and anti-reference violations.
6. Every finding cites screenshot/state plus selector or `file:line`, explains impact, gives a concrete
   repair, and states what should be preserved.

Severity remains DevX's existing vocabulary:

- `[BLOCKING]`: acceptance failure, accessibility failure, broken layout/state, hidden/unusable content,
  dead interaction, or mobile/zoom/reduced-motion behavior that prevents use;
- `[IMPORTANT]`: clear drift from the approved system/direction or visibly unfinished/inconsistent quality;
- `[NOTE]`: taste-only refinement with no acceptance/usability impact.

Do not issue subjective numeric design scores. A fix resumes the owning UI implementer and then the same
browser checker under orchestrator-guide §2a; the checker reruns the relevant functional sweep plus the
bounded visual matrix.

## 5 — Mechanical floor

- Actual contrast is checked for the rendered foreground/background pair; do not assert compliance from
  token names.
- Full keyboard path, visible focus, semantic controls/names, and no color-only meaning.
- Touch/pointer targets and 200% zoom/large-text behavior where applicable.
- Mobile overflow/landscape and dark/light contrast checked independently when supported.
- Images carry dimensions/responsive sources, correct alt behavior, and verified provenance.
- Reduced motion preserves content, state, hierarchy, and task completion.
- Third-party hotlinks are not the default: account for availability, privacy, CSP, performance, and
  license before choosing them.

Research 3–5 visual references only for a genuinely new/high-impact visual world. Do not research every
UI phase, mandate Figma, install a style generator, or force marketing-site techniques onto operational
software.
