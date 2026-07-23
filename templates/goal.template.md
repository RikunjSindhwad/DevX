<!--
GOAL (north star) — write to .devx/workstreams/{slug}/goal.md. Authored ONCE in stage 03 and
operator-gated. STABLE: phases come and go against it; this does not. A change here is a SCOPE change →
re-gate with the operator. Keep it about the WHAT (end result), never the HOW (that's the roadmap/phases).
-->

# Goal — {workstream}

## Outcome
{1–3 sentences: the end result when this workstream is DONE — the capability/behavior delivered, not the steps.}

## Definition of success
- {an observable, checkable condition that proves the outcome is met}
- {…}

## Clarified intent
<!-- Captured from the start-of-work clarification (and refreshed on any scope-changing interruption).
     This records the CLARIFIED BRIEF as the stable north star — fill every field; don't leave blanks. -->
- **Concrete outcome:** {what the operator will be able to do/see that they can't today}
- **Definition of done:** {the single condition that means "this is finished"}
- **Target users & primary workflows:** {who uses it + the few core flows it must serve well}
- **Platform / runtime constraints:** {OS, runtime, devices, offline/online, deployment target}
- **Security / data sensitivity:** {secrets, PII, untrusted/forensic input, network/auth surface — or "none notable"}
- **Acceptable tradeoffs:** {what may be sacrificed — speed vs polish, breadth vs depth, etc.}
- **Approval preference:** {autonomous end-to-end | staged operator approval at phase/scope gates}

## Constraints / non-goals
- **Must:** {hard constraints — stack/compat, security, performance, platforms}
- **Won't (explicit non-goals):** {what this workstream will explicitly NOT attempt — name them so scope can't creep}

## Pointers
{links to brief.md, decisions.md, architecture.md as relevant — read, don't restate}
