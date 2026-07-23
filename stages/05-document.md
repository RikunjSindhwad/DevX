# Stage 05 — Document (final coherence pass)

## Objective
A FINAL documentation coherence pass before ship. Docs were already synced **per phase** and a
`phases/{NN}-{slug}/summary.md` written during stage 04 (step 5 of each phase) — this stage catches
**cross-phase drift** and reconciles the top-level docs against what every phase delivered.

## Steps
1. Dispatch `devx:docs:docs` (sonnet) in **sync** mode **with NO `phase`** — the coherence variant. Sync
   without a phase runs a whole-workstream coherence pass across **all** phases (with a `phase` it would
   do a single per-phase sync + write that phase's `summary.md`; that already happened in stage 04). Pass
   the phase summaries (`phases/*/summary.md`) + the full diff so the agent reconciles README,
   `.devx/architecture.md`, and any API/usage docs **across all phases**, verifies every example/command
   actually works, and kills any cross-phase stale reference. This coherence pass writes **no** phase
   summary — it only reconciles the top-level docs. Use a fresh exact
   `return_as={NN}-docs-coherence.md`.
2. **Distill DevX/process learnings.** If `.devx/learnings.md` gained entries this workstream, dispatch
   `devx:docs:docs` in **distill** mode to refresh `.devx/learnings-index.md` (cluster prompt,
   sequencing, tool-guidance, handoff, harness/plugin, and orchestration-resource failures into ranked
   patterns) and `devx index --scope project`, using a distinct
   `return_as={NN}-docs-distill.md`. This keeps DevX's project-local process corrections searchable for
   the next agent (orchestrator-guide §11). Skip if no new learnings.
3. Read the handoffs. For each docs dispatch, run:
   ```bash
   devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}
   ```
   When both dispatches ran, validate **both exact paths** before consuming either result.
4. **Finalize (cleanup pass).** Before committing docs, ensure the workstream is production-clean
   (code-standards "Finish clean" + "Claims match artifacts"):
   - If production code carries build/phase narration (`Pxx`/`Txx`, `FP-FIX`, "MVP placeholder",
     one-off calibration notes) or dead/superseded code, views, or tests, dispatch a **cleanup
     implementer task** (then reviewer) to move narration into docs/changelog and remove the dead
     surfaces — code changes go through build+review, not docs.
   - The **docs** agent ensures README/usage claims match the quality gate that actually ran — no
     aspirational "audited/release-ready"; weaken the language or it's a defect to fix first.
   - **Tree-wide orphan backstop.** Run a whole-tree orphan check as the cross-phase net for anything
     individual phase reviews missed (per-phase cleanup happens in stage 04; this is the final catch).
     For each **non-entrypoint** module, grep the tree for inbound imports/references; flag
     **zero-importer modules**, **empty husk files**, and **leftover directories** (e.g. abandoned
     local output dirs). Identify entrypoints honestly (CLI/main/`__main__`, app/server bootstrap,
     test files, plugin/route registration discovered by the framework, build/config entry) so a
     legitimately-reachable module isn't false-flagged. A real orphan is dead surface: route it through
     a **cleanup implementer task** (then reviewer) to remove it — deletions are code changes, not docs.
5. If docs/index changes are non-trivial and VCS mode is `remote` or `local`, dispatch
   `devx:vcs:git` with `op=commit`, `commit_kind=docs`, the docs handoff paths, and an explicit `paths`
   list. In VCS mode `none`, skip git.

## Gate
None by default (auto-proceed). Surface to the operator only if docs reveal a behavior gap worth a
scope decision. (Cross-project vault **curation** is offered separately at ship — stage 06, gated.)

## Verification
- README/architecture/usage docs match the shipped diff; examples verified; no stale references.
- Tree-wide orphan check ran: no zero-importer non-entrypoint modules, empty husks, or leftover
  output dirs survive (or any kept ones are deliberately justified).
- If DevX/process learnings grew: `learnings-index.md` refreshed and project index rebuilt.

## Output artifacts
Updated docs; refreshed `learnings-index.md` (if DevX/process learnings grew); docs handoff; (optional) docs commit.

## Next
Read `stages/06-ship.md`.
