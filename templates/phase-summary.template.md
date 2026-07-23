<!--
PHASE SUMMARY — write to .devx/workstreams/{slug}/phases/{NN}-{slug}/summary.md at the END of a phase (docs).
It is the phase's HANDOFF to the NEXT phase's planner: what now exists, what's reusable, what to know.
The next phase's planner reads THIS (a pointer), not the whole phase. Keep it tight and concrete.
-->

# Phase {NN} summary — {title}

## Delivered
{what this phase actually built/changed — paths, modules, the public surface now available}

## Reusable for later phases
{functions / modules / patterns later phases should REUSE (not re-create), with `file:line`}

## Decisions
{key choices + one-line why; the chosen approach, and any notable rejected alternative}

## Verification
{tests/criteria status (actual result); GUI result if any; security verdict; Evidence checkpoint}

## For the next phase
{what the next phase should build on / avoid; any drift from the roadmap and how it was reconciled}
