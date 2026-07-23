# git / gh — version control discipline

The **git agent** owns version control and runs **native git** (no other agent runs git mutations). Its
allowlist covers the safe verbs (status/diff/log/show, switch, add, commit, push, init) + `gh pr create`
/ `gh pr view`; destructive verbs are either truly blocked or forbidden by rule (see below).

## `.devx/` exclusion (op=setup, once per repo)
DevX state is **shared** (committed) so the team sees decisions/handoffs and resume works from a fresh
clone — but transient/merge-hostile parts are handled via Read + Write (whole-file, append-if-missing).
Do **not** use grep/echo/printf/shell loops — they are not in the git agent's allowlist.

1. **`.gitignore`** — Read `.gitignore` (treat missing as empty). Ensure `.devx/cache/`,
   `.devx/index/`, and `.devx/.venv/` are present as lines. Append any missing. Write the whole file
   back. (Transient/rebuildable — caches, the FTS index, and the uv-managed env; never commit them.)
2. **`.gitattributes`** — Read `.gitattributes` (treat missing as empty). Ensure
   `.devx/log.md merge=union` and `.devx/learnings.md merge=union` are present. Append any missing.
   Write the whole file back. (Union-merge so branch merges concatenate append-only logs instead of
   conflicting.)

Both steps are idempotent — running setup twice produces the same result. Do not confuse **local VCS mode**
with private state: local mode still commits `.devx/` state locally so resume works across branches and
machines once the repo is shared. A separate private-state mode is not part of v1.

## Branch per workstream (op=branch)
First try to **resume**: `git switch devx/{slug}`. If the branch exists this switches to it — done.

If that fails (branch does not exist), **create from base**: run `git switch {base_branch}` to land on
the base branch when it exists locally (if that also fails, stay on the current branch — do not
hard-fail); then `git switch -c devx/{slug}`.

Never commit on the base branch directly. `git show-ref`, `git rev-parse`, and `git branch --list` are
not in the git agent's allowlist — use only `git switch*` to probe and create.

## Clean commits (op=commit, after a task passes review)
Stage **only** what the task changed — **never `git add -A`** (it sweeps in unrelated work). Check the
working tree first, stage the explicit paths the accepted handoff/review names, plus this workstream's
artifacts; if `git status --porcelain` shows unrelated modified files, leave them unstaged and surface
them in the handoff.
```bash
git status --porcelain                       # review first; stage explicitly, never -A
git add <explicit paths the task changed>    # the source files named in the accepted handoff/review
git add .devx/workstreams/{slug}             # this workstream's artifacts only
git commit -m "{imperative subject ≤72}" -m "{why}"
```
- **No AI-attribution.** No `Co-authored-by`, no "Generated with…", no bot emoji. History reads human.
- One coherent change per commit. No noisy WIP in the final PR.
- Never stage secrets or `.devx/cache/`. If `git status` shows something secret-looking, stop and surface it.

## PR (op=pr)

Probe before creation so an interrupted ship cannot open a duplicate:

```bash
gh pr view devx/{slug} --json url,state        # OPEN → reuse URL; CLOSED/MERGED → stop
git push -u origin devx/{slug}               # never --force
gh pr create --base "${CLAUDE_PLUGIN_OPTION_BASE_BRANCH:-main}" --head devx/{slug} \
  --title "{title}" --body "{summary from handoffs}"
```

Run `gh pr create` only after `gh pr view` clearly reports that the branch has no PR. Authentication,
repository, or network failures are not "no PR." An OPEN PR is resumed; a CLOSED/MERGED PR returns to the
orchestrator for a decision.

## Destructive ops — two tiers; gate via orchestrator if truly needed
**Truly blocked** (no allowlist pattern matches — harness refuses outright): `git reset --hard`,
`git rebase`, `git branch -D`, `git clean -fd`, `git tag -d`, history rewrite, `gh pr merge`,
`gh pr close`. The git agent cannot run these even if it tries.

**Reachable but forbidden by rule** (the `git push*` / `git add*` globs technically match — discipline,
not enforcement, stops them): never `git push --force` / `--force-with-lease`, never `git add -A` /
`git add .`. Treat these as if they were blocked.

If a truly-needed destructive op arises, surface the exact command + blast radius in the
`### Orchestrator requests` block of the handoff (agent-guide §7) and return. The orchestrator owns
all operator gates — the git sub-agent never calls AskUserQuestion directly.
