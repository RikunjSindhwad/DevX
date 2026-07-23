---
id: writing-claude-subagents
title: Writing Claude Code Subagents
type: framework
tags: [claude-code, subagents, agents, system-prompt, tool-scoping, delegation, least-privilege, fan-out, orchestration]
summary: How to author a Claude Code subagent — the definition frontmatter, a focused system prompt, a least-privilege tool allowlist, and the heuristics for when to delegate vs. work directly.
related:
  - {slug: prompt-engineering-for-claude, rel: relates-to}
  - {slug: claude-agent-skills, rel: relates-to}
  - {slug: claude-code-plugins, rel: relates-to}
  - {slug: auth-and-secrets, rel: see-also}
created: 2026-06-21
---

# Writing Claude Code Subagents

A subagent is a specialized assistant that runs in its own context window with a custom system prompt
and an optional base-tool allowlist. The parent delegates a bounded task and receives a result/summary,
which can keep verbose exploration out of the main context. Effective permissions still combine
frontmatter, parent/host policy, hooks, and the capabilities of broad tools such as `Bash`.

## Subagent Definition — the Frontmatter Fields

Subagent files are Markdown with YAML frontmatter. Store them at `.claude/agents/` (project scope, checked into version control) or `~/.claude/agents/` (user scope, all projects).

```yaml
---
name: code-reviewer          # required; unique kebab identifier; what hooks receive as agent_type
description: >               # required; when the orchestrator should delegate here
  Expert code review specialist. Proactively reviews code for quality,
  security, and maintainability. Use immediately after writing or modifying code.
tools: Read, Grep, Glob, Bash # allowlist; omit to inherit everything from the parent session
model: haiku                 # sonnet | opus | haiku | full model ID | inherit (default)
---

System prompt body goes here.
```

Only `name` and `description` are required. Every other field is optional. Key optional fields:

| Field | Purpose |
|---|---|
| `tools` | Allowlist — grant only these tools; omit to inherit all |
| `disallowedTools` | Denylist — remove specific tools from the inherited set |
| `model` | Model alias or full ID; defaults to `inherit` |
| `permissionMode` | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | Hard cap on agentic turns |
| `memory` | `user`, `project`, or `local` — enables cross-session persistent memory |
| `background` | `true` to always run as a background task |
| `isolation` | `worktree` to give the subagent a temporary git worktree |
| `skills` | Skill names to preload into context at startup |
| `hooks` | Lifecycle hooks scoped to this subagent only |
| `color` | `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, or `cyan` — sets the agent's display color in the task list / transcript; optional, no effect on behavior |

The description field is the delegation trigger. Claude reads it to decide whether to delegate a given task. Write it as a clear trigger condition — include phrases like "use proactively" or "use immediately after X" to encourage automatic delegation.

## Focused System Prompt

The Markdown body after the frontmatter supplies the role-specific instructions. A normal non-fork
subagent does not inherit the parent conversation transcript, though Claude Code may supply environment
or delegation context. Treat the installed-version documentation and a behavior probe as authoritative
for exact injected context.

Guidelines for the body:

- **One job.** State a single, bounded responsibility. A subagent that does too many things dilutes both its description trigger and its behavior.
- **Specify what to produce.** Describe the output format (e.g., "provide feedback organized by: Critical / Warnings / Suggestions").
- **State what NOT to touch.** Explicitly list off-limits actions ("you cannot modify data") to reinforce the tool constraints you set in frontmatter.
- **Give a workflow when order matters.** A numbered list of steps (1. run git diff, 2. focus on modified files, 3. begin review) helps the subagent act consistently across invocations.

For the craft of writing the prompt itself — tone, instruction clarity, avoiding ambiguity — see [[prompt-engineering-for-claude]].

## Tool Scoping (Least Privilege)

Scoping the tool surface to the minimum needed is the primary safety and focus lever for subagents.

**Allowlist with `tools`** — grant only the exact base tools or exact MCP tools the job requires. A
read-only explorer needs only `Read`, `Grep`, and `Glob`. Argument-shaped entries such as
`Read(path)`, `Write(path)`, or `Bash(command)` collapse to base-tool availability rather than
enforcing those path/argument restrictions. If you list `tools`, the subagent cannot use tools outside
that resolved list.

```yaml
tools: Read, Grep, Glob, Bash   # explicit allowlist — Write and Edit are absent
```

**Denylist with `disallowedTools`** — inherit everything from the parent session and subtract specific tools. Useful when you want most tools but want to exclude, say, Write and Edit:

```yaml
disallowedTools: Write, Edit    # keep everything else the parent has
```

If both are set, `disallowedTools` is applied first, then `tools` is resolved against the remaining pool. A tool in both lists is removed.

**MCP server patterns** — a server wildcard can grant every tool from that server, including mutations.
For read-oriented agents, enumerate the exact read tools instead. Use wildcards only after reviewing the
server's full current schema.

**The bash-vs-dedicated-tool tradeoff.** `Bash` gives breadth — the subagent can run any shell command. Use it when you need flexibility. Promote actions to dedicated tools (Read, Write, Grep, Glob, a specific MCP server tool) when you need to gate, render, audit, or parallelize them. A subagent that must never write files should omit `Write` and `Edit` even when `Bash` is present — but note that `Bash` itself can write files via shell redirection, so for a strictly read-only subagent, either omit `Bash` or add a `PreToolUse` hook to validate commands.

**Do not hand destructive tools to subagents that do not need them.** In particular, avoid `bypassPermissions` mode unless the subagent is fully trusted and the consequences of an unchecked write are acceptable. See [[auth-and-secrets]] for credential and secrets hygiene; the same principle applies to tool access.

**Hooks for conditional control.** When you need finer control than the tools field provides (for
example, allow `Bash` but only for read-only queries), use `PreToolUse` hooks with a validation script.
Prefer command exec form (`command` plus `args`) for paths, so spaces cannot change tokenization:

```yaml
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: "${CLAUDE_PROJECT_DIR}/scripts/validate-readonly-query.sh"
          args: []
```

## Delegation Heuristics — When to Spawn a Subagent

**The four-question test.** Spawn a subagent only when all four conditions hold:

1. **Complexity** — the task is multi-step and hard to fully specify up front.
2. **Value** — the outcome justifies the cost of a separate context and model call.
3. **Viability** — the current model is capable of the sub-task.
4. **Recoverable errors** — if the subagent makes a mistake, you can detect and fix it.

For a single file read or a quick question, work directly. The latency of spawning a subagent and having it re-gather context is real; for trivial tasks it is pure overhead.

**Spawn for independent and parallel workstreams.** When two or more tasks do not depend on each other's results, fan them out to subagents simultaneously:

> "Research the authentication, database, and API modules in parallel using separate subagents."

Each subagent explores its area independently; Claude synthesizes the findings. This only works well when the research paths are genuinely independent.

**Use subagents to isolate high-volume output.** Running a test suite, fetching documentation, or processing logs can consume significant context. Delegating to a subagent keeps the verbose output in the subagent's window; only the summary (failing tests, key findings) returns to the main conversation.

**Chain subagents for sequential workflows.** Each subagent completes its task and returns results; Claude passes relevant context to the next:

> "Use the code-reviewer subagent to find performance issues, then use the optimizer subagent to fix them."

**When to stay in the main conversation** — frequent back-and-forth, iterative refinement, phases that share significant context (planning -> implementation -> testing), quick targeted changes, or latency-sensitive interactions.

**Background behavior is version-sensitive.** On current Claude Code, subagents may run in the
background by default or through dispatch/frontmatter choices, and permission prompts can surface to
the operator rather than being silently denied. Do not assume background means non-interactive.
Ordinary background role agents should not rely on retaining parent task-management tools such as
`TaskCreate`/`TaskUpdate`; persist coordination in files or return it to the orchestrator.

## Fresh Context and Model Choice

**Fresh context isolation.** A non-fork subagent starts without the parent conversation transcript or
the parent's already-read file contents. The parent supplies a delegation message and receives the
result. Exact host-injected instructions and environment context are version-sensitive, so do not use
fresh context as a secrecy boundary.

An explicit forked context can inherit parent context. `isolation: worktree` is a filesystem isolation
choice, not evidence that conversation history was inherited; treat context inheritance and filesystem
isolation as separate controls.

**Model choice.** The `model` field accepts:
- Aliases such as `haiku`, `sonnet`, and `opus` — prefer aliases when following the host's
  current family mapping is desired.
- Full model IDs — pin one **only** when you need a specific, evaluated version; it will not pick up
  newer releases.
- `inherit` (the default): use the same model as the main conversation

Model override precedence is host-version-specific. Verify the current subagent reference when an
environment or per-dispatch override must win over frontmatter.

**Choose the smallest model that meets the evaluated quality bar.** Exploration can often use a faster
model, but verify routing with representative tasks rather than assuming a built-in agent's current
default or that quality is unaffected.

**Model switching is a clean task boundary.** A subagent is a useful way to evaluate or run a bounded
task on another model without mixing its working context into the parent. Treat cache behavior as an
implementation detail unless the current host documentation guarantees it.

## Example: Read-Only Code Reviewer

```yaml
---
name: code-reviewer
description: >
  Expert code review specialist. Proactively reviews code for quality,
  security, and maintainability. Use immediately after writing or modifying code.
tools: Read, Grep, Glob
model: inherit
---

You are a senior code reviewer ensuring high standards of code quality and security.

When invoked:
1. Read the supplied changed-file list and acceptance criteria
2. Inspect the changed files and relevant callers with Read, Grep, and Glob
3. Report evidence-backed findings without editing

Review checklist:
- Code is clear and readable
- No duplicated code
- Proper error handling
- No exposed secrets or API keys
- Input validation implemented
- Good test coverage

Provide feedback organized by priority:
- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider improving)

Include specific examples of how to fix issues.
```

`Write`, `Edit`, and `Bash` are absent, so the declared tool surface is read/search-only. Host policy and
any MCP grants must still be checked.

> Source: https://code.claude.com/docs/en/sub-agents · reviewed against Claude Code 2.1.218 · 2026-07-23
