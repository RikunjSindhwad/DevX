# DevX — Architecture

> A Claude Code plugin for hands-off, multi-agent software delivery. An **Opus orchestrator** attaches
> to a repository with a discoverable build and verification workflow and dispatches specialized sub-agents to **design (brainstorm/architect)
> → plan → build (TDD) → review → document → ship**, coordinating through **files in `.devx/`** and
> a local **FTS5-indexed dev-knowledge vault**, resuming cleanly across sessions.

Visual companion: [open the interactive HTML architecture diagram](./devx-architecture-diagram.html).

DevX is to software development what `web-pentest-expert` is to web pentesting. This document records
the design, what was taken and dropped from that plugin, the resolved decisions, and the rails that make
autonomy safe. It was written *after* reading the real plugin and vault on this machine and verifying
the environment (FTS5 present; `rg`, `ugrep`, and `gh` authenticated — exact versions are
environment-specific and not pinned here).

---

## 1. Design thesis

Five claims drive every choice:

1. **Files on disk are the shared brain.** Initial maker/checker lineages start isolated. Within the
   same Claude session, a bounded revision resumes the exact author/implementer and producing checker so
   they can patch/recheck without remapping; every round rereads disk. Durable continuity still lives in
   `.devx/` (append-only log, plans, and **immutable summarized handoffs**), never in an ephemeral agent id.
   Fresh fallback at a session/scope boundary is lossless because files remain canonical.
2. **The orchestrator is the only DevX dispatcher.** Current Claude Code can allow nested sub-agent
   dispatch, but DevX role agents intentionally omit the `Agent` tool. The orchestrator owns phase-level
   fan-out, joins, and write-conflict checks.
3. **Independent review is the quality engine.** Self-evaluation is unreliable (models flatter their own
   work), so a separate reviewer in a **clean context** scores each phase against **pre-committed**
   acceptance criteria. Test-first makes those criteria executable. One bounded fix pass per rejected
   verification return + a correctness floor replaces unbounded retries; a floor failure gates the human.
4. **Native tools are the executor.** `Bash/Edit/Write/Read/Grep/Glob` run the code. There is no Docker,
   SSH, or `run_tool` layer. The only custom runtime is a *retrieval* library.
5. **Subtraction, not addition.** The plugin we modeled on documented its own drift (boilerplate
   copy-pasted across 23 agents, models hardcoded in 26 files, orphaned agents). DevX single-sources the
   rules, uses model **aliases**, and ships the minimum surface that satisfies the mission.

The whole system is markdown a human can open. The only JSON is `plugin.json` (required) and
machine-readable *tool results* on stdout — never an input contract an agent must satisfy.

---

## 2. What was taken and what was dropped

Grounded in the real files under `web-pentest-expert-v3/` (and its `V3-PLAN.md` drift findings).

### From the pentest plugin

| Taken (and why) | Dropped (and why) |
|---|---|
| **Skill-as-router → staged pipeline** with progressive stage loading + operator gates (`skills/scan/SKILL.md`, `stages/00..06`) | **`runs/{engagement_id}` multi-engagement scheme** → one `.devx/` per repo + `workstreams/<slug>/` |
| **Enforced agent skeleton**: frontmatter → persona → `<important>` forced reads → Task/Done-when → Input → Steps (naming guide sections) → Output → Verification → Rules | **Copy-pasted boilerplate** (V3-PLAN F1). DevX writes the rules **once** in `references/agent-guide.md`; agents reference, never restate |
| **5-section return contract** → reworked as the **6-section handoff** (the continuity unit) | **OOB/interactsh MCP** and all blind-vuln machinery |
| **Forced lifecycle logging** (START/COMPLETE non-negotiable) | **Pentest evidence/scoring** (CVSS/OWASP/KEV/EPSS, `findings/`, `collect_findings`) — even `collect_findings` was never invoked (F6) |
| **Retrieval primitives**: `kb_search` (FTS5 cascade), `fetch` (tiered HTTP/extraction with content-class TTLs), `search` (DuckDuckGo + Bing + Yahoo by default), `github_search`, `log` (`scripts/lib/retrieval.py`, `lib/fetch/`) | **The entire execution layer**: `exec`, `run_tool`, `docker_wrapper`, `ssh_transport`, `remote_job`, `host_manager`, `container_*`, `pull_artifacts`, `job_*` |
| **Knowledge vault + external-content FTS5** (BM25, breadcrumb chunks, hash-incremental) | **`sqlite-vec` embeddings + `memory_meta`/`query_clusters`/`chunk_feedback`** — scaffolded but unused (0 rows); removed in the simplification |
| **Tools-guides** (per-tool manuals) + **templates** (fill-in artifacts) | **JSON data contracts & schema validation** (e.g. split finding frontmatter, F3) → markdown only |
| **Model tiering** (Opus brain, Sonnet workhorses, Haiku cheap) | **Pinned model strings** in 26 files (F9) → **aliases** so the plugin rides the host generation |
| **Confidence-spectrum gates** via `AskUserQuestion` | The heavy `bootstrap.py` (venv/docker/ssh detection) → a light attach stage |

### From Claude Code mechanics (verified, honored)

| Mechanic | How DevX honors it |
|---|---|
| Plugin `CLAUDE.md` is ignored at runtime | Persistent context lives in `.devx/project.md`, which the orchestrator/agents are told to read |
| Agent `tools` is an exact base-tool allowlist | DevX lists base tools honestly and enumerates read-only MCP tools; argument-shaped entries are not treated as path/command restrictions |
| Skill `allowed-tools` preapproves; it does not sandbox | Prompts, operator permissions, agent base-tool allowlists, and hooks define the effective boundary |
| Nested dispatch is possible when `Agent` is granted | DevX role agents omit `Agent`; the orchestrator remains the dispatcher and conflict coordinator |
| Agent memory is opt-in and can be persistent | DevX does not configure agent memory; handoffs + plan + `state.md` remain the portable shared brain |
| Use model aliases | `opus`/`sonnet`/`haiku` in frontmatter; opus escalation via dispatch-time override |
| `${CLAUDE_PLUGIN_ROOT}` anchors plugin files | Used everywhere for in-plugin refs; `.devx/` is relative to the repo CWD |

Compatibility baseline: the current files and strict plugin validation target Claude Code **2.1.229**.
Revalidate when upgrading the host because hook, skill, and sub-agent schemas evolve.

### From the FTS5/retrieval comparison — see §9.

---

## 3. Repository layout (expandable)

```
devx/                                  # ${CLAUDE_PLUGIN_ROOT}
├── .claude-plugin/plugin.json         # name, version, userConfig (vault_path, base_branch, github_token). No models.
├── README.md  ARCHITECTURE.md  CHANGELOG.md
├── .gitignore                         # ignore the derived FTS index/venv (the target-repo's .gitignore/.gitattributes are the git agent's job)
├── skills/
│   ├── devx/SKILL.md                  # /devx:devx — the Opus orchestrator (progressive stages + gates)
│   ├── devx-explain/SKILL.md          # /devx:devx-explain — read-only Q&A + component docs
│   ├── devx-init/SKILL.md             # /devx:devx-init — bootstrap (doctor, install, index, scaffold)
│   └── devx-vault/SKILL.md            # /devx:devx-vault — on-demand vault curation
├── stages/                            # the pipeline, loaded one at a time ("do not read ahead")
│   ├── 00-attach.md        [GATE]     # attach, .devx/ + git exclusion, scout, start/resume
│   ├── 01-design.md        [GATE,opt] # brainstorm (stack/tradeoffs→decisions.md) + architect (structure→architecture.md)
│   ├── 03-plan.md          [GATE]     # brief+arch → goal.md (north star) + roadmap.md (phase map)
│   ├── 04-build.md         (auto)     # per-phase loop: JIT plan → implement → verify band → bounded fixes → docs → commit → next phase
│   ├── 05-document.md      (light)    # final coherence pass
│   └── 06-ship.md          [GATE]     # branch / clean commits / PR + vault curation (default-on, gated)
├── agents/                            # role-based subdirs (expandable)
│   ├── recon/scout.md                 # haiku — repo map
│   ├── design/designer.md             # sonnet (opus: hard greenfield architect mode) — brainstorm|architect|plan modes
│   ├── research/researcher.md         # sonnet — web/docs/GitHub, fan-out
│   ├── build/implementer.md           # sonnet — TDD build, runs tests/lint
│   ├── review/reviewer.md             # sonnet (opus: high-risk/complex phase — CHECK role) — independent review
│   ├── security/security.md           # sonnet (opus: critical) — independent security review (per-phase verify band + whole-system pre-ship pass)
│   ├── docs/docs.md                   # sonnet — docs sync + (gated) vault curation
│   ├── ui/browser.md                  # sonnet — rendered UI verify/debug when a phase changes UI
│   └── vcs/git.md                     # haiku — exclusion, branch/commit/PR, destructive gates
├── references/                        # the plugin's OWN rules (single-sourced — anti-F1)
│   ├── agent-guide.md                 # the agent contract (logging, handoff, errors, help, retrieval)
│   ├── orchestrator-guide.md          # dispatch, gates, resume, reasoning, build loop, git
│   ├── code-standards.md              # language-agnostic quality bar
│   ├── architecture-principles.md     # modular/easy-to-change principles
│   ├── ui-design.md                   # Product Interface Direction + rendered design-quality contract
│   └── contracts/                     # canonical policy fragments (pointed-to, never restated):
│       ├── phase-verification.md      #   severity tiers, verify-band sequence, fix, floor, commit gate
│       ├── plan-check.md              #   plan-CHECK owner/challenges/verdict, dep reconciliation, re-baseline
│       └── diagnosability.md          #   runtime-shaped evidence, correlation, safe logs-to-plan diagnosis
├── tools-guide/                       # how-to manuals; volatile version facts are rechecked
│   ├── index.md
│   ├── native/{devx-cli, kb_search, git}.md
│   ├── package-managers/  test-runners/  build-lint/      # per-ecosystem (grown per project)
├── templates/                         # agent, handoff, goal/roadmap/phase, learnings, backlog, vault-entry
├── bin/devx                           # the single CLI surface (log in bash; rest → python via uv/stdlib ladder)
├── bin/codebase-memory-mcp-launcher   # plugin MCP launcher; resolves installed codebase-memory-mcp binary
├── bin/install-codebase-memory-mcp    # explicit, checksum-verified installer helper
├── .mcp.json                          # plugin-provided codebase-memory-mcp server
├── scripts/devx_lib.py                # thin CLI router (argparse + dispatch + re-exports; no business logic)
│   └── lib/                           # config, probes, retrieval, fetch/, github, validate, handoff, vault, doctor, state_check
├── hooks/{hooks.json, guard.sh, model_guard.py, token_monitor.py, _python.sh}  # model_guard PreToolUse; token_monitor SubagentStop (incl. continuations)
└── vault/                             # curated SWE knowledge, FTS5-indexed (seeded small; grows)
    ├── mdvault-devx.sqlite            # DERIVED index (git-ignored; `devx index`)
    └── languages/ frameworks/ patterns/ testing/ security/ performance/ packages/ ops/   # + emergent one-level sub-folders as a category grows
```

Expandable by design: add agents under a role dir, ecosystems under `tools-guide/`, topics under a vault
category — no code changes, just files (and `devx index` for the vault).

---

## 4. The `.devx/` project-state layout (per repo, committed/shared)

Created in the target repo at attach. **Shared via git** (team-visible decisions, cross-machine resume);
only the derived `cache/`, `index/`, and `.venv/` are ignored, and append-only logs are `merge=union` so branch
merges concatenate.

```
<repo>/.devx/
├── project.md                 # persistent project context (stack, layout, test/build cmds) — the CLAUDE.md replacement
├── log.md                     # append-only typed event log (merge=union)
├── decisions.md               # running decisions/choices (dated)
├── architecture.md            # living architecture doc
├── learnings.md               # append-only gotchas — project-local KB (merge=union)
├── learnings-index.md         # DERIVED: learnings distilled into ranked patterns (docs distill mode); FTS-indexed
├── backlog.md                 # human intake sheet: position-preserving [ ] → [~] → [x] checklist
├── workstreams/<slug>/
│   ├── brief.md               # what + why (the unit of work)
│   ├── goal.md                # north star (authored once at stage 03, gated)
│   ├── roadmap.md             # coarse phase map — one line per phase
│   ├── roadmap-check.md       # independent stage-03 roadmap critique
│   ├── state.md               # tiny resume pointer: current phase + NEXT ACTION
│   ├── research/              # pre-roadmap/brainstorm spikes only (no invented phase number)
│   ├── security-ship.md       # whole-system security pass before ship (code workstreams)
│   ├── phases/<NN>-<slug>/
│   │   ├── plan.md            # JIT per-phase plan: tasks + acceptance criteria
│   │   ├── plan-check.md      # independent phase-plan critique
│   │   ├── research/          # per-phase research + bounded, source-grounded log-diagnosis.md when used
│   │   ├── review.md          # reviewer verdict for this phase
│   │   ├── gui.md             # ui:browser verify output (when applicable)
│   │   ├── security.md        # security agent verdict (when applicable)
│   │   └── summary.md         # phase→next-phase handoff summary
│   └── handoffs/<NN>-<agent>-<task>.md   # 6-section per-agent handoffs
├── index/                     # derived project FTS5 index (mdvault-project.sqlite) (GIT-IGNORED, rebuildable)
└── cache/                     # fetch cache (GIT-IGNORED)
```

Switching repos = different CWD = different `.devx/`. No global state, no run IDs.

---

## 5. Command → skill (router) → staged pipeline

`/devx:devx` invokes `skills/devx/SKILL.md` — an Opus skill with
`disable-model-invocation: true`. Its `allowed-tools` list preapproves matching calls for the invocation;
it is not a sandbox. The skill is the orchestrator. It **loads stage docs one at a time** (`stages/NN-*.md`,
"do not read ahead") to keep its context lean, executes each, presents the gate, logs `STAGE`, and
proceeds. Standing references (`orchestrator-guide.md`, etc.) are read on demand.

### Stages & gates

| Stage | Does | Operator gate |
|---|---|---|
| 00 attach | locate/create `.devx/`, git exclusion, scout, start-vs-resume | **Workstream + mode** (always) |
| 01 design *(opt)* | brainstorm mode: stack/packages/tradeoffs → `decisions.md`; architect mode: modular structure → `architecture.md` | **Direction / Architecture** (when run) |
| 03 plan | brief+arch → `goal.md` (north star, gated once) + `roadmap.md` (coarse phase map, one line/phase) | **Goal & scope** (always) |
| 04 build | **per-phase loop**: JIT plan → implement (reuse-first + runtime-shaped diagnostics) → independent verify band → resume owning maker for bounded patch → resume producing checker for full recheck (fresh fallback on boundary) → docs/summary → commit → next phase; logs/crashes route through bounded source diagnosis | only on ambiguity / scope change / floor failure |
| 05 document | final coherence pass | none (auto) |
| 06 ship | branch/commits/PR + vault curation (default-on, gated) | **Ship + curate** (always) |

Minimum always-on gates: **goal/scope** (stage 03) and **ship** (stage 06). The design gate appears
only when the design stage (optional) runs. **Build is autonomous** — that is where "hands-off" lives.
Planning is just-in-time: each phase is planned immediately before it is built, not all up front. The
human owns **direction, scope, and shipping**; the machine owns execution.

### Graph-shaped orchestration, deliberately framework-free

DevX is an explicit execution graph without a graph-framework dependency: role agents and deterministic
gates are nodes; stage/risk/verdict routes are edges; `.devx/` artifacts are the typed-enough durable state;
exact handoff paths are completion barriers; the roadmap is the stop condition; operator gates are
human-in-the-loop interrupts. Safe tasks fan out only over disjoint write/resource sets and fan in only
after **every pre-allocated exact handoff** validates.

This is a legibility description, not a redesign or rename. File-based state fits a single-repository
plugin: it is inspectable, commit-friendly, and resumable without another runtime. The LLM keeps autonomy
inside bounded nodes, while deterministic code owns fragile checks such as handoff validation, state
consistency, and vault promotion. A graph framework, durable workflow engine, voting swarm, or more agents
would add cost without improving the current scale.

### Second entry point — `/devx:devx-explain`
A read-only sibling skill for understanding an existing codebase, with no pipeline: **ASK** mode answers
questions over the repo + vault with `file:line` citations and flow traces; **DOCUMENT** mode generates
per-component docs (`docs/components/*.md`) by fanning out one `docs` agent per component (clean context
each) + an index. Reuses scout + docs + the vault. This is the brownfield onboarding / "doc every
component" capability.

### Bootstrap skill — `/devx:devx-init` (OPTIONAL)
`/devx:devx` is the self-sufficient entry point: it scaffolds `.devx/`, initializes git if absent, dispatches
the repo scout, chooses a VCS mode, and starts or resumes a workstream — no prior setup required.

`/devx:devx-init` is an OPTIONAL, non-agentic bootstrap that can be run before first use on a new
machine or project. It does NOT dispatch sub-agents (no `vcs:git`, no `recon:scout`). What it does
directly: invokes `devx doctor` (checks/installs required and optional tools after confirmation, FTS5
absence is a DEGRADED warning not a blocker), runs `git init` via Bash if no `.git` exists (bare init
only), builds the vault FTS5 index, verifies optional code graph MCP availability, and scaffolds a minimal `.devx/` stub (project.md
placeholder, backlog.md, empty log/decisions/learnings). It then instructs the operator to run `/devx:devx`,
which does the rest: git exclusion setup (`op=setup` via `vcs:git`), real repo scouting (fills
`project.md` via `recon:scout`), VCS-mode selection, and workstream creation. `/devx:devx-init` is never
required before `/devx:devx` — it is an acceleration aid for explicit tool-install and index-prebuild steps.

---

## 6. Agent roster & the enforced contract

The orchestrator is a skill (Opus). Nine sub-agents, each mapping to a required role; none orphaned.

| Agent | Model | Base tools and enumerated MCP access | Reads | Trigger |
|---|---|---|---|---|
| `recon:scout` | **haiku** | Read, Grep, Glob, Bash + read-only graph tools | agent-guide, diagnosability | attach/resume repo map; bounded logs-to-source diagnosis |
| `design:designer` | **sonnet** *(opus: high-judgment design/plan cases in §6)* | Read, Write, Edit, Grep, Glob, Bash, WebSearch + read-only graph tools | agent-guide, architecture-principles, code-standards, vault/packages, vault/patterns | greenfield / new feature / structure refresh; modes: `brainstorm` \| `architect` \| `plan` |
| `research:researcher` | **sonnet** | Read, Write, Edit, Grep, Glob, Bash, WebSearch + read-only graph tools | agent-guide | "requesting help" / gaps (fan-out) |
| `build:implementer` | **sonnet** | Read, Write, Edit, Grep, Glob, Bash + read-only graph tools | agent-guide, code-standards, plan, tools-guide | per plan task |
| `review:reviewer` | **sonnet** *(opus: check — prompt-constrained read-only)* | Read, Write, Grep, Glob, Bash + read-only graph tools | agent-guide, code-standards, plan, vault/security | per-phase verify band |
| `security:security` | **sonnet** *(opus: critical/deep; prompt-constrained read-only)* | Read, Write, Grep, Glob, Bash + read-only graph tools | agent-guide, code-standards, vault/security | per-phase verify band + whole-system pre-ship pass |
| `docs:docs` | **sonnet** | Read, Write, Edit, Grep, Glob, Bash + read-only graph tools | agent-guide, code-standards, vault/README | after review / gated curation |
| `ui:browser` | **sonnet** | Read, Write, Edit, Grep, Glob, Bash | agent-guide, ui-design, tools-guide/native/playwright | rendered UI verification/debug when a phase changes UI |
| `vcs:git` | **haiku** | Read, Write, Edit, Grep, Glob, Bash | agent-guide, tools-guide/native/git | branch/commit/PR/exclusion |

The frontmatter list controls which base tools exist for an agent; it cannot express path- or
argument-scoped variants such as `Write(.devx/**)` or `Bash(git status)`. Each role's prompt declares
its intended paths and commands, while operator permissions and hooks remain the enforceable outer
boundary. The code-graph grants enumerate read-only tools; mutation tools are not granted to role agents.

### Model policy: PROPOSE → MAKE → CHECK → FIX (orchestrator-guide §6a)

**Opus reasons/designs and checks; sonnet makes product source; haiku does plumbing. Opus never
mutates product source.** An opus designer may author `.devx/` architecture/plan/check artifacts—the
judgment output—but not code, tests, app configuration, migrations, or runtime assets.

- **PROPOSE / DESIGN** — opus orchestrator or designer reads the roadmap + context and directs: which
  phase, what acceptance criteria, which agents to dispatch. The designer may persist that judgment
  under `.devx/`.
- **MAKE** — sonnet implementer writes code, tests, and docs. Haiku handles VCS plumbing and repo
  scouting.
- **CHECK** — an initially separate opus/sonnet reviewer lineage (independent, read-only) judges against
  pre-committed criteria, then may resume for patch closure. No source edit, ever. This is the anti-flattery rail.
- **FIX** — the owning sonnet implementer resumes for one fix pass on the current rejected return. If the
  floor is not met after that pass, the operator gates. There is no 2-strike debug pass and no automatic
  opus retry escalation — the bounded fix-pass rule + the floor replace them.

**Every Opus assignment justified (cost):**
- **Orchestrator (opus, standing):** one long-lived brain that reasons, dispatches, and steers. The
  single most leverage point; everything else flows from its judgment.
- **Reviewer → opus (CHECK role, not standing):** independent read-only check per phase. Opus is the
  checker because self-review by the maker (sonnet) is unreliable.
- **Designer → opus for high-judgment cases (not standing):** initial/hard greenfield architecture,
  hard phase plans, GUI/UX, security-critical, concurrency/device/hardware design, and independent checks
  of those plans. Its write boundary remains `.devx/` judgment artifacts.

That is the entire Opus budget: one standing orchestrator + on-demand designer/reviewer/security judgment.
Sonnet does the work; haiku does the cheap, high-frequency, rule-following work (repo mapping, VCS plumbing).

An external Codex second opinion is not another roster agent or a verification gate. When internal evidence
materially conflicts, a stabilized diff is security-critical/high-blast-radius, or the operator requests
it, the orchestrator may ask permission for one inline, read-only `codex exec … -o …` review. Its artifact
is advisory and every retained claim returns through the normal DevX verifier.

### The enforced contract (single-sourced in `references/agent-guide.md`)

Every agent: (1) **logs START first, COMPLETE last** (non-negotiable — the resume trail); (2) reads the
mandatory references named in its `<important>` block, citing sections (e.g. "agent-guide §3");
(3) follows defined **Steps** (often naming the guide section to apply); (4) on failure runs the
**error protocol** → appends to `.devx/learnings.md` only for a DevX/process root cause; (5) ends by writing **one summarized handoff**;
(6) includes an **Evidence checkpoint** in Verification, forcing a post-evidence reasoning update;
(7) surfaces human decisions and help requests via `### Orchestrator requests` — it cannot gate or
dispatch; the **orchestrator** owns `AskUserQuestion` and dispatch. Agents are not free-form: the
skeleton + the single-source guide are the discipline.

---

## 7. The handoff contract (the unit of continuity)

Each agent's entire output is **one handoff** — summarized, so the next worker starts clean. Template:
`templates/handoff.template.md`. Six fixed sections:

> **Phase-level continuity:** in addition to the per-agent 6-section handoff, each completed phase
> writes `phases/{NN}-{slug}/summary.md` (from `templates/phase-summary.template.md`). This is the
> **phase → next-phase handoff** — what the JIT planner for the next phase reads to understand what
> was built, what was deferred, and what the correctness floor confirmed. The 6-section handoff remains
> the per-agent unit; `summary.md` is the per-phase unit.

| Section | Content |
|---|---|
| **Summary** | 2–4 sentences: what was done, the outcome |
| **Changes** | Files created/edited (paths), tests added, commands run |
| **Decisions** | Choices + one-line why; what downstream must know (name the next agent); optional `### Orchestrator requests` |
| **Verification** | Tests/linters run + **actual** result; acceptance-criteria status; any test-first exception; Evidence checkpoint |
| **Issues** | What failed/skipped/uncertain — or "none" |
| **Next** | The single **NEXT ACTION**, blockers, and exact files the next worker must read |

Path: `.devx/workstreams/<slug>/handoffs/<NN>-<agent>-<task>.md`. **Context-budget rule:** once a detail
is on disk, keep only a one-line pointer in context (the generalized "evidence-to-disk" rule from the
pentest plugin's evidence standard).

---

## 8. The append-only log

`devx log TYPE SOURCE "MESSAGE"` appends one line to `.devx/log.md`:

```
[2026-06-20T08:27:38Z] START reviewer — review T03 round 1
```

`log` is **pure bash** in `bin/devx` (no Python, no venv) so lifecycle logging never breaks; the append
is atomic for lines < 4 KiB (O_APPEND). Types: `START`/`COMPLETE` (agents); `DISPATCH`/`GATE`/`DECISION`/
`STAGE`/`NOTE` (orchestrator). The log + `state.md` are the resume spine. `merge=union` keeps the log
sane across workstream branches.

DISPATCH messages carry `workstream=<slug> agent=<agent> return_as=<exact-file.md>`. The structured tokens
make the advisory state audit workstream-scoped and let resume reconstruct the exact fan-in barrier instead
of inferring completion from same-role file counts.

Append-only is a **convention**, not a globally tool-enforced guarantee: lifecycle writes go through
`devx log`, and role prompts declare ownership of handoffs and durable files. Agent frontmatter exposes
base tools, not path-scoped `Write(...)` grants, so operator permissions and prompt compliance remain
part of the boundary. The Bash hook guards its narrow catastrophic-command denylist; it does not
intercept `Write` or `Edit`.

---

## 9. Retrieval architecture (resolved)

Three corpora, three answers. Comparison uses the verified facts and what the live vault shows.

| Option | Verdict for DevX |
|---|---|
| **SQLite FTS5 (BM25)** | **Chosen for the curated vault.** In-process, single file, BM25 out of the box, `snippet()`, phrase/prefix, no service. Verified present here (`CREATE VIRTUAL TABLE … fts5` succeeds); the proven `mdvault` already uses it. |
| **ripgrep / ugrep** | **Chosen for source code + as the vault fallback + project-memory tier.** No index, never stale, native. `ugrep` for long-line files to avoid OOM. No ranking — that's why FTS5 sits in front for the vault. |
| **Embeddings / vector DB** (`sqlite-vec`, Chroma, …) | **Removed.** Was scaffolded (`chunks_vec`, `memory_meta`) and never used (0 rows). The hybrid/RRF semantic tier has been cut; `vec` table, `DEVX_EMBED_*` env vars, and embedding code are gone. FTS5 BM25 + ripgrep + the links graph is the complete retrieval stack. |
| **Tantivy / Turso / Solr-ES / `LIKE`** | **No.** Separate engine/JVM/service or experimental FTS for marginal gain at single-user, single-repo scale; `LIKE` has no ranking. |

**Resolved stack:** **FTS5 (BM25) for the curated vault; ripgrep for source, for the vault fallback, and
for project memory. Embeddings/semantic tier removed — this is the complete stack.**

A deliberate **durable-vs-volatile split** (refining the spec's "FTS5 for vault *and* project memory"):
we FTS-index the durable project knowledge but not the volatile coordination files. `index --scope
project` builds an FTS5 index over `phases/*/research/`, `learnings.md`, `decisions.md`,
`architecture.md`, `project.md` (stable, append-mostly, worth ranking) into `.devx/index/`
(git-ignored, rebuildable). The volatile files — `log.md`, `state.md`, `handoffs/` — change every run;
indexing them would be stale within one agent, so `kb_search` reaches them via the ripgrep tier. Net:
`--scope vault` (default) = FTS5 vault cascade; `--scope project` = FTS5 project index + ripgrep
fallback; `--scope all` = both, FTS-first. **This is what makes per-phase research and learnings logged
by one phase rank for later phases** — the compounding loop, project-local and automatic.

### The cascade (verified working)
`devx kb_search` runs **FTS5(vault) → ripgrep(vault) if thin**, and under `--scope project|all` also
**FTS5(project) → ripgrep(.devx) if thin** — FTS hits ranked ahead of ripgrep, short-circuiting at 3
good hits. It **probes** FTS5 and falls back to ripgrep on `no such module fts5` or a missing DB. Queries are sanitized (free text → quoted tokens) so hyphens/CVE-IDs/slashes never
break FTS5. Hits carry a `path > H1 > H2` breadcrumb and a `snippet()`. Smoke-tested: `"test first red
green refactor"` → the TDD chunk at bm25 −11.4; `"idor authorization object level"` → the OWASP
access-control section at −11.1.

### The lean library surface (`bin/devx` + `scripts/devx_lib.py` → `scripts/lib/`)
`devx_lib.py` is a thin **CLI router** (~160 lines: argparse + dispatch + re-exports, no business logic);
each subsystem is its own module under `scripts/lib/` — `config`, `probes`, `retrieval`, `fetch/` (extract/
http_client/tiers/web_search), `github`, `validate`, `handoff`, `vault`, `doctor`, `state_check`.
(Modeled on the pentest plugin's router-over-`lib/` split.) Command surface:
`kb_search`, `fetch`, `search`, `github_search`, `index` (Python) + `log` (bash) form the base retrieval/index/log surface. Core gates: `validate` (promotion validation gate), `handoff_check` (handoff continuity gate), `state check` (state.md consistency gate). Optional accelerators: `codebase-memory-mcp` (source graph MCP for reuse/dedup discovery), `ast-grep` (structural search), `vault stats` (vault layout distribution + "time to split" signal). Operator commands: `doctor` (env preflight: verifies required tools python≥3.11/git/rg — sqlite3-fts5 is strongly recommended but degraded, not required — reports optional codebase-memory-mcp/ast-grep/ugrep/gh, emits OS install hints, exits non-zero on missing required tools). The
boundary vs native tools:
- **`fetch` kept** — now a **modular subsystem** in `scripts/lib/fetch/` (`extract`/`http_client`/`tiers`):
  a tiered cascade (`github-raw → urllib → requests-if-installed → Wayback`) + an extraction cascade
  (`trafilatura → BeautifulSoup → stdlib strip`) over a content-hash cache under
  `.devx/cache/fetch/`. Cache reads honor content-class TTLs (news/releases about 1 day, specs about
  90 days, default about 14 days); `--refresh` forces a miss. Optional deps are import-guarded, so
  absent them it degrades to the `urllib` + regex-strip floor.
- **`github_search` kept** — native tools **cannot** do GitHub *code* search; finding real usage is high
  value for dev. Uses `gh` (when authenticated).
- **`search` kept** — **multi-engine** in `scripts/lib/fetch/web_search.py`: DuckDuckGo, Bing, and Yahoo
  are queried by default and RRF-fused/deduped; `--engines` narrows the set. Native `WebSearch` remains
  the alternative if the local engines fail.
- **`index` kept** — we *own* the vault, so we own its (rebuild-on-demand, hash-incremental) builder.
- **`log` is bash** — too important to depend on Python.

---

## 10. The three-layer knowledge structure & KB lifecycle

| Layer | What | Where | Retrieval |
|---|---|---|---|
| **references/** | the plugin's **own operating rules** (agent contract, orchestrator rules, code standards, architecture principles) | plugin | read directly (cited by `<important>` blocks) |
| **tools-guide/** | **how-to manuals** for the working tools (the `devx` CLI, git, package managers, test runners, linters); volatile details say when to recheck live help/docs | plugin | read before using a tool |
| **vault/** | **curated SWE knowledge** (languages, frameworks, patterns, testing, security, performance, packages, ops); entries carry YAML frontmatter (`id`/`title`/`tags`/`related`/…) and cross-link via `related:`/`[[wikilinks]]` (a `links` graph) | plugin (or `vault_path`) | `devx kb_search` (FTS5) |

### Coordination structure (per repo)

| File | Role | Distinct from |
|---|---|---|
| `.devx/backlog.md` | **The work queue** — operator intake; bugs/improvements waiting to become workstreams; marked done with a result link | `log.md` (event trail), `state.md` (per-workstream resume pointer) |
| `.devx/log.md` | Append-only typed event trail (START/COMPLETE/GATE/…) | the backlog (no status workflow, no result links) |
| `.devx/workstreams/<slug>/state.md` | Per-workstream resume pointer (NEXT ACTION) | the backlog (one row per workstream, not per task) |
| `phases/{NN}-{slug}/plan.md` | JIT per-phase tasks + acceptance criteria (planned immediately before each phase is built) | the backlog (scoped to one workstream's execution) |

### Lifecycle (curated global + project-local, with a gated write-back loop)
- **Curated/global vault** *(default-on growth, gated)* — seeded small (a few real exemplars now),
  shared across all projects. The
  `devx validate <candidate.md> --promote-to <target.md>` **gate** is the *sole automated promotion
  writer*; maintainers may deliberately edit the source Markdown and own the same editorial checks.
  Vault growth happens three ways: (1) deliberate maintainer curation; (2) **default-on
  operator-gated promotion** at ship (stage 06 proposes curation; operator approves or skips);
  (3) **`/devx:devx-vault`** on demand (paste content or research a topic). All three converge on the same
  gate. The kb_search read and validate gate are core; the ship-time curation is default-on.
- **Project-local memory** — `.devx/learnings.md` accumulates only DevX/process root causes; product
  failures stay in their phase/review/backlog artifacts. It and research/decisions are **FTS5-indexed**
  (`index --scope project`), so they
  ranks for the next agent via `kb_search --scope project`.
- **Write-back loop (self-improving):** every **agent-assisted** path feeds the global vault **through
  the `devx validate <candidate.md> --promote-to <target.md>` gate** (the CLI is the sole automated promotion writer; agents hold
  no direct vault-write contract). (1)
  **Research candidate** — the **researcher** may stage a generalizable, *authoritative* candidate
  (official docs/specs, stripped of project specifics, provenance-tagged `> Source: … · candidate · date`)
  and request orchestrator/operator approval before promotion. (2) **Curate at ship** — the **docs** agent
  in *curate* mode promotes accumulated `learnings.md` lessons the same way. (3) **On demand** — the
  **`/devx:devx-vault`** skill lets the operator paste content or research a topic and promote it (same
  template, same gate) without waiting for a ship.
  Candidates are **frontmatter'd** (per `templates/vault-entry.template.md`), so the gate dedups on `title`
  (not just H1) and resolves `related:`/`[[wikilinks]]` against the indexed `links` graph — a dangling
  internal link is a **warning** (target may be promoted next), never a block. The gate checks mechanical
  signals—provenance/date, definitive dead links, collisions, absolute-path leakage, and internal-link
  resolution—but does not prove that content is true or authoritative. Curators must still judge source
  quality and correctness. There is **no dedicated `kb-curator` agent**
  (folded into researcher/docs/`/devx:devx-vault`).

---

## 11. Git handling (the `git` agent)

The only agent that runs git mutations. VCS mode and defaults:
- **Local git is the default floor**: if the repo has no `.git`, DevX initializes one. All work happens
  on a branch with commits — no push, no PR. This is the mode you get without any explicit choice.
- **Remote is opt-in**: at attach the operator is asked whether to enable remote (push + PR via `gh`).
  Declining keeps local. The mode is **changeable anytime** — switch local→remote (or back) later.
- **"none" skips git entirely** (still available; useful for scratch/ephemeral repos), but is no longer
  the default.
- **`.devx/` shared via git**: committed for team visibility + cross-machine resume.
  `op=setup` git-ignores only the derived `.devx/cache/`, `.devx/index/`, and `.devx/.venv/` (uv env) and sets `.devx/log.md`/`learnings.md` to `merge=union` so
  branch merges concatenate append-only files instead of conflicting. (If a project prefers local-only
  state, it switches to `.git/info/exclude` — the alternative the design supports.)
- **Branch per workstream**: `devx/<slug>` off `base_branch`; never commit on base directly.
- **Clean commits**: imperative subject ≤72, a "why" body, **no AI-attribution** (`Co-authored-by`,
  "Generated with…") — history reads as human work. Never stage secrets or cache.
- **Typed commit contracts**: prompt-level `commit_kind=phase|docs|final-state` selects the required
  verification artifacts and explicit staging set; this is not a DevX CLI flag.
- **State before commit/push**: phase status is reconciled before its commit; curation, backlog,
  `security-ship.md`, and final state are committed before remote push/PR. The PR result is then recorded
  and pushed as the final durable ship result.
- **PR via `gh`** at ship when remote mode is active, body summarized from handoffs. The git agent probes
  `gh pr view devx/<slug> --json url,state` first: OPEN is resumed, no-PR creates, CLOSED/MERGED returns to
  the operator, so interrupted shipping cannot silently duplicate a PR.
- **Destructive ops gated**: `push --force`, `reset --hard`, `branch -D`, history rewrite → present the
  exact command + blast radius via `AskUserQuestion`. The thin `PreToolUse` net also refuses these if
  attempted outside the agent.

---

## 12. Start / resume

**Start:** `/devx:devx [goal]` → Stage 00 detects no `.devx/`, scaffolds it, scouts the repo into
`project.md`, defines a workstream, gates on workstream+mode, and enters the pipeline.

**Resume (files only, never chat history):** Stage 00 finds `.devx/`, reads `log.md` (tail) +
`workstreams/<slug>/state.md` (NEXT ACTION) + `roadmap.md`, and infers where the pipeline stopped from
**which phase summaries and handoffs exist**. It confirms with the operator and continues from the NEXT
ACTION. A crash, a new machine, or a fresh clone loses nothing that wasn't on disk — which, because
`.devx/` is committed, is everything that matters. Before replaying the pointer, the orchestrator probes
the intended durable result (exact handoff, latest commit, existing PR, or promotion target); a completed
result is reconciled, an absent result is retried, and partial/ambiguous state returns to a gate.

---

## 13. How hands-off autonomy is achieved (and the rails)

**Autonomy:** each agent owns its domain end-to-end (embeds its own tools, retries, error handling via
agent-guide §4) and returns a summarized handoff. The orchestrator dispatches, reads handoffs (paths,
not contents), updates the NEXT ACTION, and proceeds. Between the few gates, Stage 04 runs the
per-phase loop (JIT plan → implement → verify band → bounded fixes → docs → commit → next phase) without
human input. Fan-out (parallel researchers/implementers in one message) keeps it moving.

**Rails that make it safe:**
1. **Independent review** in a clean context against pre-committed criteria — the anti-flattery rail
   (PROPOSE→MAKE→CHECK→FIX model policy).
2. **Bounded fix passes + correctness floor** — the implementer gets exactly one fix attempt for each
   rejected verification return; if the correctness floor is not met on re-verification, the operator
   gates. Never an automatic infinite loop; reset beats patching a tired context.
3. **Test-first + live-verify** — acceptance criteria are executable before code; the reviewer re-runs
   them, and runnable changes are confirmed by actually running the app (harness `verify`/`run`) before commit.
4. **Minimal base-tool allowlists + explicit role contracts** — reviewers are instructed not to edit
   source, mutation-capable graph tools are not granted, destructive Bash commands hit the hook denylist,
   and curated-vault writes go through the `devx validate` gate. Host permissions remain authoritative.
5. **Operator gates** on direction, scope, and shipping — the human steers the *what*, not the *how*.
6. **Forced logging + summarized handoffs + `state.md`** — every step is on disk; resume is trivial.
7. **Thin `PreToolUse` net** — refuses a tiny denylist of catastrophic commands at the main level.
8. **Git destructive-op gates** — irreversible VCS actions need explicit approval.

---

## 14. Anti-goals ledger (deliberately NOT built)

| Not built | Why |
|---|---|
| `exec`/`run_tool`/container/SSH execution layer | Native `Bash/Edit/Write/Grep/Glob` is the executor |
| JSON data contracts / schema validation | Markdown a human reads (except `plugin.json`); stdout JSON is a result, not a contract |
| Embeddings / vector DB | FTS5 + ripgrep + the links graph is the complete stack; the semantic tier was removed (was scaffolded and never used) |
| A giant pre-populated vault | Structure + index + `kb_search` + growth process now; a handful of real exemplars, not hundreds |
| Agent sprawl | `tester`→implementer (TDD); `debugger`→bounded-fix+floor behavior (PROPOSE→MAKE→CHECK→FIX); `kb-curator`→docs curate-mode. Every surviving agent is dispatched (no F6 orphans) |
| Agent Teams / multi-session orchestration | Single orchestrator + sub-agents is enough for v1; noted as a future option |
| A bespoke permission/policy engine | Base-tool allowlists + role prompts + host permissions + a thin `PreToolUse` net + operator gates |
| Pinned model version strings | Aliases (`opus`/`sonnet`/`haiku`) so the plugin rides the host generation (fixes F9) |
| Restated rules across agents | Single-sourced in `references/` (fixes F1, the pentest plugin's root drift) |

---

## 15. Verification performed while designing

Verified via `pytest -q`, `devx index --scope vault`, and `devx doctor` — exact tool versions and index
counts are environment-specific and not pinned here.

- FTS5 available (probe succeeds); `rg`, `ugrep`, `python`, and `gh` present and authenticated.
- `devx index` built the vault; incremental reindex reported `changed: 0` on re-run then a non-zero
  count after adding files (hash-incremental works).
- `devx kb_search` returns correctly-ranked FTS5 hits with breadcrumbs + snippets, and falls back to
  ripgrep when FTS5 is thin.
- `devx github_search` returns real code via `gh`; `devx log` writes the exact line format to `.devx/`.

Current release changes and historical design notes are summarized in `CHANGELOG.md`.

---

## 16. v0.2 — improvement loops (compounding knowledge)

Added so the system gets better as it works, not just within a single run:

| Addition | What it does | Where |
|---|---|---|
| **Project knowledge index** | `index --scope project` builds an FTS5 index over *durable* `.devx` knowledge (research/learnings/decisions/architecture/project); `kb_search --scope project` is now **ranked**, not just grep. A lesson one agent logs **ranks** for the next. Volatile files (log/state/handoffs) stay ripgrep-only. | `devx_lib.py`, `00-attach` (build after scout), `.devx/index/` (git-ignored) |
| **Research candidates → gated vault promotion** | The researcher stages generalized, primary-source-backed candidates and requests promotion; the orchestrator/operator decide whether shared knowledge should change. Approved agent candidates enter through `devx validate <candidate.md> --promote-to <target.md>`, which checks mechanical signals and then writes + reindexes. Editorial review still owns truth and source authority. | `agents/research/researcher.md`, `vault/README.md` |
| **Live-run + verify** | Green tests aren't enough: runnable changes are confirmed by actually running the app (project run command or the harness `verify`/`run` skill; screenshot for UI) before commit. A live-verify failure is part of the per-phase verify band; it counts as the CHECK rejection and triggers that verification return's bounded fix pass. | `04-build` (live-verify step), `agent-guide §5`, `skills/devx` (`Skill` tool), implementer/reviewer |
| **Explain / onboarding + component docs** | `/devx:devx-explain`: read-only ASK (cited Q&A over repo + vault) and DOCUMENT (fan-out one `docs` agent per component → `docs/components/*.md` + index). | `skills/devx-explain/SKILL.md`, `agents/docs/docs.md` (*map* mode) |

**Forward-propagation within a run** was already designed (learnings on failure, handoffs, decisions,
`--scope project`) — the project index upgrades it from passive grep to ranked retrieval.

**Documented next steps (not built):** *active learning injection* (orchestrator auto-injects relevant
learnings into every brief), *deps & security freshness* pass, *PR-comment responder*. These are
additive and fit the existing roster (no new agents needed) when wanted.

**Re-verified after these changes:** project FTS index builds (durable files only; log/state excluded),
`kb_search --scope project` ranks a logged learning above ripgrep, `--scope all` ranks FTS ahead of
ripgrep, the whole-word fallback removed substring noise, and the vault path stayed green.

---

## 17. v0.3 — robustness & compounding (gated loops, tests)

Five additions hardening the loops, drawn from a comparative review of the `claudekit-engineer` plugin:

| Addition | What it does | Where |
|---|---|---|
| **Auto-promote validation gate** | `devx validate FILE --promote-to CAT/NAME.md` is the required agent-assisted promotion path. It rejects definitive 404/410 source links, missing provenance, collisions (by title/filename), and absolute project-path leakage; warns on transient link failures, age, and dangling internal links; then writes + reindexes on PASS. It is a structural gate, not a truth or source-authority verifier. | `devx_lib.py` (`validate_promotion`, `cmd_validate`), `researcher.md`, `docs.md` (curate), `orchestrator-guide §11` |
| **Handoff continuity check** | `devx handoff_check` validates that a returning agent actually wrote a complete handoff (6 sections + Status); exits non-zero → orchestrator re-dispatches. Protects resume, the run's only memory. | `devx_lib.py` (`_validate_handoff`, `cmd_handoff_check`), `orchestrator-guide §3`, `04-build`, `agent-guide §3` |
| **Learnings distillation** | `docs` *distill* mode clusters the append-only `learnings.md` one-offs into ranked, generalized **patterns** in `learnings-index.md` (back-pointered, FTS-indexed via `PROJECT_TOP`). A recurring lesson now *ranks*, instead of staying buried among one-offs. | `docs.md` (distill), `templates/learnings-index.template.md`, `devx_lib.py` (`PROJECT_TOP`), `05-document` |
| **Per-phase JIT plans** | Planning is just-in-time: stage 03 produces `goal.md` + `roadmap.md` (one line/phase); for each phase, the designer + researcher fan out to produce `phases/{NN}-{slug}/plan.md` immediately before that phase is built. An implementer/reviewer is handed one phase plan, not the whole roadmap — keeping each dispatch context-sized. (Supersedes the earlier directory-based `plan/phase-NN-*.md` approach.) | `designer.md` (plan mode), `templates/goal|roadmap|phase-summary.template.md`, `03-plan`, `04-build`, `implementer.md`, `reviewer.md` |
| **Self-tests** | A per-module `pytest` suite (one `test_*.py` per `lib/` module) over the router + `lib/` — chunker, incremental index/prune, FTS search, ripgrep whole-word fallback, kb_search ranking/dedup/scopes, fetch/search/github_search, all gates, plus **adversarial** cases (path-traversal, invalid-status, delete-then-readd). | `tests/`, `requirements-dev.txt` |

### Prompt hardening & KB (from the same `claudekit-engineer` content review)

A follow-on pass mined claudekit's agent prompts, journals, and skills for non-architectural value:

| Addition | What it does | Where |
|---|---|---|
| **Anti-rationalization guardrails** | Turn "evidence over assertion" from a principle into enforceable patterns: a no-performative-agreement rule, an Excuse→Reality table ("should work now" → run it; "the other agent said it passed" → re-verify), and a "letter *and* spirit / no synonym-dodging" clause. Touches every agent (esp. the reviewer). | `agent-guide §5` |
| **Root-cause + three-strike stop** | Fix the cause not the symptom (trace to the trigger); after 3 failed attempts, **stop guessing** and escalate instead of patching. | `agent-guide §4`, `implementer.md` |
| **Reviewer blast-radius scout** | The reviewer greps callers/dependents, hunts the same bug elsewhere, and checks async/shared-state interactions the criteria don't cover — "don't trust 'simple changes'." | `reviewer.md` (step 4) |
| **Frustration-as-signal** | Operator phrases like "stop guessing"/"ultrathink this" are read as *the approach is wrong* — reconsider fundamentals, don't fire another patch. | `agent-guide §8` |
| **Inversion (option generation)** | The designer (brainstorm mode) flips a problem ("make the failure impossible") to surface non-obvious options before recommending. | `designer.md` |
| **Problem-solving techniques (vault KB)** | The one genuinely reusable knowledge doc ported in — a generalized, language-agnostic taxonomy (simplification cascade, collision zone, meta-pattern, inversion, scale game) with a symptom→technique table. | `vault/patterns/problem-solving-techniques.md` |

Vault scope decision: **kept SWE-only.** claudekit's best content was *agent/context-engineering*
meta-knowledge; that belongs in DevX's own authoring discipline (prompts/guide), not a vault the delivery
agents query for the target codebase. Only the cross-over (problem-solving thinking) was curated.

**Reviewed-but-deferred** (deliberately not built): secret-exfiltration guard (operator deprioritized),
a numeric review cycle-cap with auto-approve threshold, a single schema'd config (`.devx/config.json`),
a context-cost ignore file, and an end-to-end dogfood run. All are additive.

**Verified after these changes:** `pytest -q` is green (per-module suite); the validate gate rejects missing-provenance
and dead-link candidates (exit 1) and promotes a clean one (writes + reindexes); `handoff_check` passes a
6-section handoff and fails a truncated one; `learnings-index.md` is picked up by the project index.

---

## 18. Review remediation + source graph discovery

A documentation/robustness review surfaced gaps between the docs and `scripts/devx_lib.py`. The code was
hardened and the docs reconciled to match reality:

| Hardened | Now true in the code |
|---|---|
| **userConfig wired** | `vault_dir()` reads `CLAUDE_PLUGIN_OPTION_VAULT_PATH` (→ `DEVX_VAULT_PATH` → plugin-root default); `github_search` maps `CLAUDE_PLUGIN_OPTION_GITHUB_TOKEN` → `GH_TOKEN`. The `userConfig` block is no longer cosmetic. |
| **Validation gate is path-safe** | `validate --promote-to` constrains the target to inside the vault — `../`, absolute paths, and symlink escapes are rejected (writes only under `vault/`). |
| **`handoff_check` enforces `Status:`** | A valid `Status:` (one of `complete` \| `partial` \| `blocked`) is required; `ok` is false (exit non-zero) without it, even when all six sections are present. |
| **FTS prune bug fixed** | A deleted file's chunks are removed on reindex; no rowid-reuse misattribution. |

### codebase-memory-mcp

DevX removed its custom `devx codemap` CLI and uses `codebase-memory-mcp` as the preferred source graph
for reuse/dedup discovery. The plugin declares the MCP in `.mcp.json`; Claude Code starts it when the
plugin is enabled, provided the binary is installed. Plugin-bundled MCP tools use the official
plugin-prefixed form, for example `mcp__plugin_devx_codebase-memory-mcp__search_graph`.

The graph answers "does this already exist?" before agents write code, and also supports snippets,
call-path tracing, duplicate/similar-code queries, architecture overviews, and changed-file impact. Agents
still confirm load-bearing claims against the live working tree with `rg`/`ast-grep` because any external
index can lag untracked or mid-edit files.

Installation is explicit, not silent. `devx doctor` reports the binary as optional-missing and
`/devx:devx-init` offers the bundled installer helper, which downloads the release, verifies
`checksums.txt`, and installs to `~/.local/bin` unless the operator chooses another path.

Target repos should add `.cbmignore` for non-product folders such as `.devx/`, `.codebase-memory/`,
`node_modules/`, `dist/`, `build/`, `coverage/`, `.turbo/`, and generated/vendor trees that would pollute
source discovery.

---

## 19. Vault frontmatter + link graph, and `/devx:devx-vault`

A recheck against a much richer **reference vault** (300 docs: frontmatter + FTS5 + a `links` graph +
dormant feedback scaffolding) showed DevX's bundled vault was the lean subset (files / chunks /
`chunks_fts`). We took the two highest-value, lowest-cost ideas and dropped the rest:

| Idea | Verdict | Why |
|---|---|---|
| **Structured frontmatter** (`id`, `title`, `type`, `tags`, `summary`, `related`, `created`) | **Taken** | Stronger dedup key (by `title`, not just H1), better snippets, and it carries the cross-refs. SWE-adapted (no pentest fields). Stdlib regex parse — no YAML dependency. |
| **Typed `related`/`[[wikilink]]` graph + a `links` table** | **Taken** | This is the operator's "no-dup + wikilinks followed": `devx index` builds the `links` table; `devx validate` resolves targets and **warns** on dangling ones. |
| **`chunks_vec` semantic search** (`sqlite-vec`) | **Removed** | Was scaffolded and never used (0 rows). The semantic/hybrid tier (`vec` table, `DEVX_EMBED_*`, RRF fusion) has been cut. FTS5 BM25 + the links graph is the complete stack; no upgrade path. |
| **`query_clusters` / `chunk_feedback` / `memory_meta`** | **Skipped** | Dormant (0 rows) even in the reference — feedback/clustering machinery not earning its keep. |

**What changed in code:**

| Component | Change |
|---|---|
| `lib/retrieval.py` | Added `_frontmatter`/`_fm_field`/`_extract_links` (frontmatter `related:` slugs + inline `[[wikilinks]]`) and a `links(file_id, target)` table to the schema. `_build_index` populates it (replaced on file change, pruned on delete) and reports a `links` count in stats. |
| `lib/validate.py` | Dedup now keys on frontmatter `title:` (falling back to H1); added `_vault_slugs()` (frontmatter `id` + filename stem) and a **§5 internal-links check** — a `related:`/`[[…]]` target that resolves to no known vault id/title is a `dangling-links` **warning**, never a failure. New `vault_slugs` param + `dangling_links` in the result. |
| `skills/devx-vault/SKILL.md` | New operator skill. **PASTE** mode generalizes content the operator hands it; **RESEARCH** mode researches a topic (`devx search`/`fetch`) and synthesizes. Both author a frontmatter'd candidate under `.devx/cache/promote/` and promote through `devx validate <candidate.md> --promote-to <target.md>` — the skill is **not** a vault writer, the gate is. |
| `templates/vault-entry.template.md` | The entry shape (frontmatter + body + provenance) shared by `/devx:devx-vault` and the docs agent's curate mode. |
| `agents/docs/docs.md` | Curate mode now authors entries from the template (frontmatter + `related`) and treats `dangling-links` as a non-blocking warning. |

The gate stays the **sole automated promotion writer** and **path-safe** (writes only under `vault/`);
the upgrade makes candidates richer and dedup/cross-linking smarter. Maintainer source edits remain an
explicitly manual path.

### Layout: emergent sub-folders (the brain doesn't navigate by folder)
The concern raised next was the *directory* shape — `vault/patterns/` becoming a flat folder of hundreds of
`.md` files as it grows. The resolution (operator-chosen) is a **policy, not an engine change**, because
retrieval never touches the tree: `kb_search` hits the FTS index + tags + the `links` graph, and the indexer
globs `**/*.md`. So a flat folder hurts *human browsing*, not findability.

- **The eight categories are the stable top level.** Within a category, structure **emerges**: stay flat
  until it's clearly large, then split natural clusters into **one level of sub-folders**
  (`languages/python/asyncio.md`, `patterns/resilience/circuit-breaker.md`). No code change was needed —
  nested `--promote-to`, the `_within` clamp, breadcrumbs, and dedup-by-basename already handle depth.
- **Folders are coarse navigation; metadata is the real axis** (`type`/`tags`/`related`/search). We
  deliberately do **not** pre-build a deep taxonomy (early guesses age badly) or flatten to one tag-only dir
  (just relocates the junk drawer, loses per-category git/PR scoping).
- **`devx vault stats`** *(optional curation aid, `lib/vault.py`)* reports the per-category distribution
  (total + directly-held counts + sub-folder breakdown) and flags any folder holding more than
  `--split-threshold` files *directly* (default 20) as a "time to split" signal — so reorganizing is a
  human decision made with data, applied when warranted, never an automatic move. Disk is the source of
  truth (works with no index); index counts are best-effort enrichment.

**Verified:** `pytest -q` green — the frontmatter/link-graph coverage above plus
`devx vault stats` (counts, sub-folder breakdown, oversized-flag + split-suggestion at a custom threshold,
oversized sub-folder, index enrichment); end-to-end through `bin/devx`: a nested `--promote-to
patterns/distributed/saga-pattern.md` passed the gate, and `vault stats` flagged an oversized flat category.
