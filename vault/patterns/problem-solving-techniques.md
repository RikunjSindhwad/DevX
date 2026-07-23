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

> Source: DevX curated knowledge · curated · 2026-06-20
