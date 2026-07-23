# Stage 06 — Ship

## Objective
Get the work reviewable by a human: clean commits on the workstream branch — and, in **remote** VCS mode,
a pushed branch + PR — plus optionally folding generalizable DevX/process learnings back into the vault. The VCS mode
(remote | local | none) was chosen by the operator at attach (`project.md`); honor it, defaulting to
**local** (the floor set at attach). The operator may still switch modes here. Operator-gated.

## Steps
1. Confirm exit state: every `roadmap.md` phase is done (each plan→verify→fix→docs→state reconciliation,
   plus commit when VCS is enabled), suite green, docs reconciled (`state.md` / `roadmap.md` / phase summaries).
2. **Final security pass (whole-system).** Per-phase security already ran in the build loop (04, step 3);
   here dispatch `devx:security:security` with `scope=full` (the full `devx/{slug}` diff) for a whole-system
   pass that catches **cross-phase / integration** issues a single-phase review can't see. `scope=full`
   takes **NO `phase_slug`** and writes its report to `.devx/workstreams/{slug}/security-ship.md` (per-phase
   security writes `phases/{NN}-{slug}/security.md` instead) — give the agent that output target and a fresh
   exact `return_as={NN}-security-ship.md`. It returns
   severity-ranked findings (`file:line` + fix) + dependency audit + secret scan. On return,
   `devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}`. **Critical/High
   findings stop automated shipping** → route back into the build loop. If one survives its bounded fix,
   only the explicit operator security-risk acceptance defined by `phase-verification.md` §V4 can proceed;
   record it before the ship gate. Medium/Low surface at the gate. Skip only for no-code changes (pure
   docs); dispatch at **opus** for a security-critical system.
3. **Optional external second opinion, only when materially useful.** After the internal report and
   stabilized diff exist, the orchestrator may recommend a Codex CLI code/security second opinion only for
   unresolved conflicting evidence, a security-critical/high-blast-radius diff, or an operator request.
   Ask the operator first; default is decline. If approved, follow
   `${CLAUDE_PLUGIN_ROOT}/tools-guide/native/codex-review.md`, write
   `.devx/workstreams/{slug}/codex-ship-review.md`, and independently verify any material finding. The
   advisory output neither replaces `security-ship.md` nor changes the ship verdict by itself.
4. **Ship gate** (AskUserQuestion). Default the ship action to the **VCS mode chosen at attach**
   (`project.md`). Local is the floor — if attach chose local, default here is local. The operator
   may upgrade (local → remote, which will ensure/ask for a remote first) or downgrade (remote →
   local) here; switching to remote when no remote is configured surfaces that requirement first.
   ```
   Workstream {slug} ready.
   - Phases: {N} done, all verify bands passed   - Tests: {summary}   - Branch: devx/{slug}
   - Security: {clean | M Medium/Low | K Critical/High → fixed | explicitly accepted per §V4}
   - VCS mode (from attach): {remote (origin: {url}) | local | none}   ← you can change it here
   Ship as (default = attach VCS mode):
     Remote → push + open a PR to {base_branch}   ·   Local → keep clean commits, no push/PR  [default if attach=local]
     ·   None → nothing to push/commit
   Also: promote {M} generalizable DevX/process learnings to the vault?  [yes — default] / no
   ```
   Log `GATE` + `DECISION`.
5. **Curate before finalizing state (default — gated).** Vault growth is **on by default** (the ship gate's curate question
   defaults to **yes**) so each shipped workstream feeds its generalizable findings — including the
   per-phase research and any generalizable DevX/process learnings — back into the vault; the operator can
   decline. When confirmed, dispatch `devx:docs:docs` in **curate** mode → it generalizes the chosen
   `.devx/learnings.md` process entries + durable per-phase research (strip project specifics), with a
   fresh exact `return_as={NN}-docs-curate.md`, and stages
   each candidate under
   `.devx/cache/promote/`. On return, run
   `devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}`.
   Promotion happens ONLY through the promotion validation gate:
   `devx validate .devx/cache/promote/{candidate}.md --promote-to {cat}/{name}.md`.
   That gate is the sole automated promotion writer: it checks definitive dead links, provenance,
   collisions, absolute-path leakage, and link resolution, then writes the vault + reindexes only on
   PASS. It does not prove truth or source authority; curate against primary evidence. Never write into the vault category
   directly and never run `devx index` here — the gate owns the write and the reindex.
6. **Close the backlog item before the final-state commit (if applicable).** If this workstream was started from a backlog item,
   Edit `.devx/backlog.md` to mark the item done: change its `- [~]` (in-progress, set at attach) to
   `- [x]` — completing the `[ ] → [~] → [x]` lifecycle (orchestrator-guide §12) — and append a result
   link (PR url, branch name, or handoff summary), e.g.:
   ```
   - [x] {item text} <!-- done: {branch name | handoff summary}; PR pending when remote -->
   ```
   Skip if the workstream had no associated backlog item.
7. **Reconcile and commit final durable state before any remote push.**
   - Run `devx state check --workstream {slug}` after curation/backlog reconciliation.
   - **Local:** set `state.md` complete and log the local ship result, then dispatch `devx:vcs:git` with
     `op=commit`, `commit_kind=final-state`, explicit final artifact paths, and a fresh exact
     `return_as={NN}-git-final-state.md`. The branch is the deliverable.
   - **Remote:** set `state.md` NEXT ACTION to `"open PR"` and log `"ship prepared"`; dispatch the same
     `commit_kind=final-state` operation before any push.
   - **None:** skip git, set `state.md` complete, and log the no-VCS completion.

8. **Execute the remote action last, when selected.** Dispatch `devx:vcs:git op=pr` with a fresh exact
   `return_as={NN}-git-pr.md` to push `devx/{slug}` and create or resume a PR to `base_branch` with the
   handoff-derived summary. If no remote is configured,
   surface that and return to the operator's mode choice; do not silently claim a local fallback.
   The git agent first probes for an existing PR; an OPEN PR is resumed, while CLOSED/MERGED returns to the
   operator rather than creating a duplicate. After an existing or newly-created OPEN PR supplies the URL,
   the agent changes `state.md` from `"open PR"` to complete, updates the backlog result link when applicable,
   commits those small ship-result artifacts, and pushes the follow-up commit so the remote branch is
   durably complete.

   For every Remote or Local git return, run:
   ```bash
   devx handoff_check .devx/workstreams/{slug}/handoffs/{return_as}
   ```

## Verification
- The chosen ship action succeeded for the VCS mode: **remote** → PR exists (`gh pr view`); **local** →
  clean commits on `devx/{slug}` (`git log`); **none** → n/a.
- No secrets or `.devx/cache/` committed; commit history clean (no AI-attribution).
- Security review ran on code changes; every Critical/High finding was fixed or has the explicit
  operator acceptance + tracked follow-up required by `phase-verification.md` §V4.
- If curated: candidates passed
  `devx validate .devx/cache/promote/{candidate}.md --promote-to {cat}/{name}.md` (gate generalized,
  wrote the vault, and reindexed on PASS).
- If workstream came from a backlog item: `.devx/backlog.md` was edited to mark the item `- [x]` with
  a result link recorded.

## Output artifacts
PR (or commits/no-VCS durable state); updated vault + index (if curated); final `state.md`; ship log entry;
updated `.devx/backlog.md` (if workstream was backlog-sourced); optional `codex-ship-review.md` only when
operator-approved.

## Completion
Present the summary: workstream, tasks done, test/coverage, PR link, DevX/process learnings captured,
deferred items.
