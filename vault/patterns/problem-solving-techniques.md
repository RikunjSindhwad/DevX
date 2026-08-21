---
id: problem-solving-techniques
title: Problem-Solving Techniques (when you're stuck)
type: pattern
tags: [problem-solving, debugging, design, reasoning]
summary: A small set of reasoning moves for matching stuck symptoms to better debugging or design approaches.
related: []
created: 2026-06-20
---

# Problem-Solving Techniques (when you're stuck)

A small toolkit of named moves for getting unstuck on a design or debugging problem. Language- and
domain-agnostic. The point is to **match the symptom to a technique** instead of pushing harder on an
approach that isn't working.

## When stuck → which technique
| Symptom | Try |
|---|---|
| Solution keeps growing more cases/branches/flags | **Simplification cascade** |
| Two requirements seem to contradict each other | **Collision zone** |
| "I've solved something like this before" | **Meta-pattern recognition** |
| Boxed in by an assumption ("we must handle X") | **Inversion** |
| Works for 1, unclear at 1,000 (or vice-versa) | **Scale game** |
| Three fixes haven't worked | **Stop** — question the approach, don't patch again |

## Simplification cascade
Each simplification unlocks the next. Don't optimize the current design — ask what makes a whole branch
of it unnecessary. Remove a case, and the special-casing around it often disappears too.
- **Do:** "What would let me delete this entire code path / config option / state?"
- **Red flag you need it:** the fix adds a flag or an `if` for every new requirement.

## Collision zone
When two forces conflict (fast *and* consistent; flexible *and* simple), the resolution is usually a
**third framing**, not a compromise on a slider. Make the conflict explicit and look for the move that
dissolves it (e.g. make the slow path rare rather than choosing slow-vs-stale).
- **Do:** state both forces in one sentence, then ask "what makes this tradeoff not apply?"

## Meta-pattern recognition
Abstract the current problem to its shape and ask where you've seen that shape. A rate limiter, a
connection pool, and a semaphore are the same resource-budget pattern; a retry, a circuit breaker, and a
cache are all "avoid repeating expensive work." Reuse the known solution's structure.
- **Do:** describe the problem without domain nouns; the analogy that pops out is the lead.

## Inversion
Flip the problem to surface a non-obvious option, then pick.
- "Handle the error" → **make the error impossible** (types, contracts, making invalid states unrepresentable).
- "Make it fast" → **what makes it slow?** Remove that.
- "How do we add X?" → **what would we remove so X isn't needed?**
- **Do:** generate with inversion *before* narrowing to a recommendation.

## Scale game
Deliberately change the scale by orders of magnitude and re-ask. A design good for 10 items often breaks
at 10M (and vice-versa: an "enterprise" design is overkill for 10). Push to the extreme to find where the
approach actually breaks.
- **Do:** "At 1000×, what's the first thing that breaks?" and "At 1×, what's the simplest thing that works?"

## The discipline behind all of them
- **Root cause, not symptom.** Fix at the source; a patch at the error site resurfaces elsewhere.
- **Know when to stop.** Three failed attempts means the *approach* is wrong — stop, reconsider
  fundamentals, and escalate. More blind fixes make things worse.

## Label every claim with its verification state

When an investigation produces findings, force each one into exactly three buckets:

| label | meaning |
|---|---|
| `CONFIRMED` | reproduced; the exact command and observed output are recorded |
| `NEEDS-DYNAMIC-TESTING` | plausible, not reproduced; what blocked it is stated |
| `THEORETICAL` | the pattern matches but no reachable path was established |

Applied mid-investigation across several parallel agents, this changed behaviour immediately:
they began isolating claims with negative controls instead of asserting them, and several
self-downgraded their own earlier findings. The label is cheap and it makes over-claiming
visible rather than rhetorical. Introduce it in the **initial** brief, not as a correction.

## A control that reads correct in source may be inert on a parallel path

The highest-value bug in one investigation was a status filter that looked, statically, like a
working access control — and *was* one, on one of two execution engines. The second engine never
read the value the guard set, because a comment explained the filter had been "already considered"
upstream. Reading the guard confirmed it worked. Only running the same request against both
engines showed one returning private content and the other not.

**Technique:** when a system has two or more interchangeable implementations of the same operation
(engines, backends, code paths, cache tiers, fast/slow paths), never verify a control on one and
generalise. Run the identical input through each and diff the outputs. The asymmetry *is* the bug,
and it is invisible to source reading because each path looks locally correct.

This is the inverse of the [[#Collision zone]] idea: instead of looking where two things meet, look
where two things that should be equivalent quietly are not.

## Test the cheap claim instead of reasoning about it

If a claim can be settled by one command and a live environment exists, reasoning about it is a
false economy. In one audit three separate well-argued conclusions were each overturned by a single
test — two of which changed the top finding's severity, and one of which was a plausible-sounding
escalation that did not exist at all. The reasoning was not sloppy; it was just unverified.

Corollary: a negative result needs the same scrutiny as a positive one. An off-by-one in a test
payload produces silence that is indistinguishable from "not vulnerable." When a test fails to
reproduce, first prove the test itself reached the code under test.

> Source: DevX curated knowledge · curated · 2026-06-20 · extended 2026-07-25
