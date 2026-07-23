<!--
DEVX AGENT TEMPLATE — the canonical skeleton every agent follows (see ARCHITECTURE §6 "enforced contract").
Copy this to agents/{role}/{name}.md and fill it in. Keep it CLEAR and CONCISE — an agent is a focused
worker, not an essay. The rules live ONCE in references/agent-guide.md; reference them, never restate them.

Key conventions:
  • description: is the DISPATCH SIGNAL — write it so the orchestrator knows WHEN to use this agent, what it
    does, and what it returns. This is the most important line in the file.
  • model: is an ALIAS (haiku | sonnet | opus) — never a pinned model string. Cheapest tier that does the job.
  • tools: are EXACT BASE TOOL NAMES or exact MCP names — only what this agent needs. Argument-shaped
    forms such as `Write(path)` and `Bash(command)` do not enforce path/command scope; put intended
    ownership in the role prompt and rely on host permissions/hooks for enforcement.
  • Sub-agents have NO AskUserQuestion and CANNOT dispatch — surface human decisions/help via
    `### Orchestrator requests` in the handoff (agent-guide §7). The orchestrator owns gates and dispatch.
  • Every agent logs START first / COMPLETE last and ends with ONE handoff that includes an Evidence
    checkpoint (templates/handoff.template.md; agent-guide §13).
-->
---
name: {agent-name}                 # lowercase; dispatched as {role}:{name}
description: >
  {WHEN the orchestrator should dispatch this agent + WHAT it does + WHAT it returns. One tight paragraph —
  this is what the orchestrator routes on.}
model: {haiku | sonnet | opus}     # alias only; note in the line if the orchestrator may escalate (e.g. opus on a high-risk/complex phase)
color: {color}
tools:                             # exact base names / exact MCP names only
  - Read
  - Write                         # role text below constrains intended output paths
  - Glob
  - Grep
  - Bash
  # … add only required base tools (e.g. Edit, WebSearch) and exact read-only MCP tools
---

# {agent-name}

{One- or two-sentence persona: what this agent is responsible for and the line it does not cross
(e.g. "you design — you don't implement"). Concise and concrete.}

<important>
1. `${CLAUDE_PLUGIN_ROOT}/references/agent-guide.md` — §1 logging, §3 handoff, §4 error protocol +
   DevX/process learnings, §6 inputs, §7 orchestrator requests, §13 Evidence Checkpoint.
2. {role-specific forced reads — e.g. code-standards.md, architecture-principles.md, a tools-guide, a vault dir}
</important>

## Task
{The single outcome this agent produces.}

**Done when**: {the objective, checkable completion condition}. START/COMPLETE logged.

## Input
<!-- The dispatch params the orchestrator provides. Standard context reading (project.md → brief/phase/
     handoffs → decisions/architecture) is single-sourced in agent-guide §6 — don't restate it; list the
     params specific to THIS agent. Multi-mode agents: add a `mode` row + which inputs each mode needs.
     Source/trust and missing/stale behavior follow agent-guide §6; make deviations explicit here. -->
| Name | Required | Source / trust | Missing or stale behavior | Description |
|---|---|---|---|---|
| workstream | yes | Orchestrator control | Stop: `MISSING_REQUIRED_INPUT` | Slug (→ handoff path) |
| return_as | yes | Orchestrator control | Stop: `MISSING_REQUIRED_INPUT` | Exact unique handoff filename |
| {param} | {yes/no/for X} | {control/evidence source} | {stop/continue/refresh} | {what it is} |

## Steps
1. `devx log START {agent-name} "{what}"`.
2. {numbered steps; name the guide section to apply where it helps, e.g. "(agent-guide §5)"; read inputs per §6}.
3. …
<!-- On failure: run the error protocol. Append to .devx/learnings.md only for DevX/process/prompt/
     sequencing/tooling/handoff/resource lessons per agent-guide §4; product-code bugs stay in the handoff,
     review/security artifacts, summary, or backlog. -->

## Output
{artifacts produced} + a handoff per `${CLAUDE_PLUGIN_ROOT}/templates/handoff.template.md` →
`.devx/workstreams/{workstream}/handoffs/{NN}-{agent-name}-{tag}.md`.

## Verification
- {how this agent confirms its own work is real — verify before claiming (agent-guide §5), with evidence}.
- Evidence checkpoint: {confirmed | revised | invalidated} — {concrete artifact/result/source and how it changed or confirmed the next step}.
- `devx log COMPLETE {agent-name} "{summary}"`.

## Rules
- {the few non-obvious constraints specific to this agent — keep them sharp; the general contract is in agent-guide}.
- No `AskUserQuestion` / no dispatch — route human decisions via `### Orchestrator requests` (agent-guide §7).
