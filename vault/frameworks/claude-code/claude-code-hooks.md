---
id: claude-code-hooks
title: Claude Code Hooks (hooks.json)
type: framework
tags: [claude-code, hooks, hooks-json, lifecycle-events, matcher, pretooluse, permissiondecision, plugins, mcp]
summary: How to configure Claude Code lifecycle hooks — hooks.json shape, matcher syntax, command exec form, stdin/output contracts, and version-sensitive event behavior.
related:
  - {slug: claude-code-plugins, rel: relates-to}
  - {slug: claude-agent-skills, rel: relates-to}
  - {slug: writing-claude-subagents, rel: relates-to}
created: 2026-07-03
---

# Claude Code Hooks (hooks.json)

Hooks let Claude Code (and plugins) observe or intercept lifecycle events — a tool call about to run, a
session starting, a turn ending — and run a command, HTTP call, MCP tool, or LLM check in response. Hooks
are the enforcement layer: unlike a system-prompt instruction, a hook can actually **block** an action
(deny a tool call, stop a turn) because Claude Code evaluates its exit code / JSON output deterministically,
not by asking the model to comply. Use a hook wherever a rule must hold every time, not just when the model
remembers to follow it — validating a command before it runs, injecting context at session start,
enforcing a lint/format pass after every edit.

## Configuration shape

`hooks/hooks.json` (project: `.claude/settings.json`'s `hooks` key; plugin: `hooks/hooks.json` at the
plugin root) nests three levels: event → matcher groups →
handlers.

```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "<pattern>",
        "hooks": [
          { "type": "command", "command": "/absolute/path/to/check", "args": [], "timeout": 30 }
        ]
      }
    ]
  }
}
```

A plugin's `hooks/hooks.json` may also carry a top-level `description` field (shown in the `/hooks` menu).

## Hook events

The event set grows across Claude Code releases. The following are representative; verify the exhaustive
list, matcher fields, and blocking behavior against the installed version's official hook reference:

| Event | Fires | Matches on | Can block? |
|---|---|---|---|
| `SessionStart` | Session begins/resumes | `startup`\|`resume`\|`clear`\|`compact` | No (context-injection only) |
| `UserPromptSubmit` | User submits a prompt, before Claude sees it | none (always fires) | Yes — blocks + erases the prompt |
| `PreToolUse` | Before a tool call executes | tool name (`Bash`, `mcp__server__tool`, …) | Yes — richest control, see below |
| `PostToolUse` | After a tool call succeeds | tool name | No hard block (tool already ran); can give feedback or rewrite output |
| `PostToolUseFailure` | After a tool call fails | tool name | No |
| `Notification` | Claude Code sends a notification | `permission_prompt`\|`idle_prompt`\|`auth_success`\|… | No |
| `SubagentStart` / `SubagentStop` | A subagent spawns / finishes | agent type name | `SubagentStop`: yes, same pattern as `Stop` |
| `Stop` | Main agent finishes responding | none | Yes — prevents stopping |
| `PreCompact` / `PostCompact` | Before/after context compaction | `manual`\|`auto` | `PreCompact`: yes — blocks compaction |
| `SessionEnd` | Session terminates | reason (`clear`\|`resume`\|`logout`\|…) | No |
| `FileChanged` | A watched file changes on disk | literal filenames, e.g. `.envrc\|.env` | No |
| `WorktreeCreate` | A worktree is being created | none | Yes — any non-zero exit fails creation |
| `ConfigChange` | A config file changes mid-session | `user_settings`\|`project_settings`\|`local_settings`\|`skills`\|… | Yes, except `policy_settings` (never blockable) |
| `Elicitation` / `ElicitationResult` | MCP server requests/receives user input | MCP server name | Yes — can accept/decline/override on the user's behalf |

Additional events (`Setup`, `InstructionsLoaded`, `UserPromptExpansion`, `MessageDisplay`,
`PermissionRequest`, `PermissionDenied`, `PostToolBatch`, `TaskCreated`, `TaskCompleted`, `StopFailure`,
`TeammateIdle`, `CwdChanged`, `WorktreeRemove`, and others) cover narrower cases (task lifecycle, API-error
turns, teammate idling, permission-dialog interception). See the official hooks reference for the
exhaustive, current list and per-event field details — the event set has grown over time and is not
frozen.

Some events do not accept a `matcher` and always fire. This list has changed between releases; do not
copy a counted list into policy. Check the current event's reference before adding a matcher.

## Matcher syntax

How a `matcher` string is evaluated depends on its characters:

| Matcher value | Evaluated as |
|---|---|
| `*`, `""`, or omitted | Match everything — fires on every occurrence of the event |
| Only letters/digits/`_`/`-`/spaces/`,`/`\|` | Exact string, or a `\|`/`,`-separated list of exact strings |
| Any other character | JavaScript regex, unanchored (`RegExp.prototype.test`) — anchor with `^...$` for a whole-string match |

For tool events (`PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`,
`PermissionDenied`) the matcher runs against `tool_name`; other events match on their own field
(`source` for `SessionStart`, `notification_type` for `Notification`, `agent_type` for agent events, etc).

**MCP tools** are named `mcp__<server>__<tool>`; to match every tool from a server use
`mcp__<server>__.*` — a bare `mcp__<server>` is compared as an *exact string* and matches nothing.

**Per-handler finer filtering:** the `if` field on an individual handler (permission-rule syntax, e.g.
`Bash(git *)`, `Edit(*.ts)`) is evaluated only on tool events, narrower than the group's `matcher`. It
**fails open** (runs the hook) if the command can't be parsed — treat it as a filter, not a hard security
boundary; use permission rules (`permissions.deny`) for that.

## Handler types

Every handler in a matcher group's `hooks` array has a `type` and runs in parallel with the others
(identical handlers are deduplicated: command hooks by `command`+`args`, HTTP hooks by URL).

| Type | Key fields | Input | Output |
|---|---|---|---|
| `command` | `command` (required); `args` (array — presence switches to *exec form*: no shell, no quoting needed; absence = *shell form*, string passed to `sh -c`/PowerShell); `async`, `asyncRewake`, `shell` | JSON on **stdin** | exit code + stdout/stderr |
| `http` | `url` (required); `headers` (supports `$VAR` interpolation only for names in `allowedEnvVars`); `allowedEnvVars` | JSON as the **POST body** | HTTP status + response body (same JSON schema as `command`) |
| `mcp_tool` | `server` (required, must already be connected), `tool` (required), `input` (supports `${tool_input.field}` substitution) | tool call | tool's text content, parsed like command stdout |
| `prompt` | `prompt` (required, `$ARGUMENTS` placeholder for the hook's input JSON), `model` (defaults to a fast model) | — | single-turn LLM yes/no JSON decision |
| `agent` | same fields as `prompt` | — | spawns a read-only subagent (Read/Grep/Glob) to verify a condition — **experimental** |

Timeout defaults vary by handler and event. Set an explicit, short timeout appropriate to the check and
verify current limits in the installed-version documentation.

**HTTP hooks cannot hard-block via status code alone**: a non-2xx response, connection failure, or
timeout is a *non-blocking* error (execution continues) — to hard-block, return 2xx with a JSON body
carrying `decision: "block"` or `hookSpecificOutput.permissionDecision: "deny"`.

## Input contract (stdin JSON)

Every hook event receives at least: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, and (once
a prompt has been submitted) `prompt_id`. Tool events add `tool_name` and `tool_input`; `PostToolUse`
additionally adds `tool_response` and `duration_ms`; `Stop`/`SubagentStop` add `stop_hook_active` and
`last_assistant_message`.

```json
{
  "session_id": "abc123",
  "cwd": "/home/user/my-project",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": { "command": "npm test" }
}
```

## Output contract: exit codes and JSON

**Exit codes** (command/HTTP hooks):

- **Exit 0** — success. Claude Code parses stdout as JSON *only* on exit 0. For most events plain stdout
  goes to the debug log only; exceptions where it's surfaced to Claude directly: `UserPromptSubmit`,
  `UserPromptExpansion`, `SessionStart`.
- **Exit 2** — blocking error. Any stdout/JSON is **ignored**; stderr is fed back to Claude as an error
  message. Effect is event-specific: blocks the call for `PreToolUse`, prevents stopping for
  `Stop`/`SubagentStop`, has **no effect** for `PostToolUse`, `Notification`, `SessionStart`, and several
  other non-blockable events.
- **Any other non-zero exit** — non-blocking error for most events (a "hook error" notice, execution
  continues) — **except `WorktreeCreate`**, where any non-zero exit aborts the worktree creation.

**JSON output** (exit 0, stdout is exactly a JSON object) — universal fields on every event:

| Field | Default | Effect |
|---|---|---|
| `continue` | `true` | `false` stops Claude entirely after the hook — overrides any event-specific decision |
| `stopReason` | none | Shown to the user (not to Claude) when `continue:false` |
| `suppressOutput` | `false` | Hides stdout from the transcript (still logged) |
| `systemMessage` | none | Warning shown to the user |

**`hookSpecificOutput`** carries the per-event decision. For `PreToolUse` — the canonical allow/deny/ask
control:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by hook"
  }
}
```

`permissionDecision` is one of `allow` (skips the prompt, except for tools that always require
interaction), `deny` (blocks the call), `ask` (prompts the user, labeled by source), or `defer`
(non-interactive `-p` mode only). Deny/ask permission *rules* still apply regardless of what a hook
returns. When multiple `PreToolUse` hooks disagree, precedence is **`deny > defer > ask > allow`**.

**Migration note — read this before writing a new `PreToolUse` hook.** `PreToolUse` used to signal its
decision via **top-level** `decision`/`reason` (values `approve`/`block`). That form is **deprecated** —
use `hookSpecificOutput.permissionDecision`/`permissionDecisionReason` instead (`approve`→`allow`,
`block`→`deny`). This split is real and current, not a docs typo: **other events keep the older top-level
form** — `PostToolUse`, `Stop`, `UserPromptSubmit`, `PostToolBatch`, `ConfigChange`, and `PreCompact`
still use plain `decision: "block"` / `reason` (no `hookSpecificOutput` wrapper). Only `PreToolUse` (and
`PermissionRequest`, which nests under `hookSpecificOutput.decision.{behavior, ...}`) moved to the newer
shape.

## `${CLAUDE_PLUGIN_ROOT}` and friends

Three placeholders substitute inline in a hook `command`/`url`/`prompt` and are exported as real
environment variables to the spawned process:

| Variable | Resolves to |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | The plugin's install directory (changes on every plugin update — don't write state here) |
| `${CLAUDE_PLUGIN_DATA}` | Persistent data dir surviving updates (`~/.claude/plugins/data/{id}/`) — use for caches, installed deps |
| `${CLAUDE_PROJECT_DIR}` | The project root |

Prefer **exec form** (set `args`) for any hook referencing a path placeholder — no shell tokenization
means no quoting needed even for paths containing spaces. In **shell form**, wrap the placeholder in
double quotes. Plugin hooks additionally substitute `${user_config.*}` from the plugin's `userConfig`
schema.

## Plugin hooks merge (union) with user/project hooks

When a plugin is enabled, its hooks **merge with** the user's and project's hooks — this is a union, not
an override. Concretely, hook sources (ascending scope) are: `~/.claude/settings.json` (user),
`.claude/settings.json` (project), `.claude/settings.local.json` (local), managed policy settings, plugin
`hooks/hooks.json`, and skill/agent frontmatter. For any firing event+matcher, **every matching handler
from every source runs in parallel** — there's no "last one wins," and disabling one source doesn't
suppress another. The `/hooks` menu labels each configured hook with its source (`User`, `Project`,
`Local`, `Plugin`, `Session`, `Built-in`) so you can see where it came from.

Related settings an author/operator should know: `disableAllHooks` (disables all hooks from that scope
down — only a *managed*-scope setting can disable managed-source hooks) and `allowManagedHooksOnly`
(managed settings only — strips user/project/most-plugin hooks except those force-enabled via managed
`enabledPlugins`).

## Gotchas

- **Lifecycle-end hooks have tight time budgets.** Keep them fast and set an explicit supported timeout;
  do not depend on an undocumented environment override.
- **`if` is a filter, not a security boundary.** It fails open on unparseable Bash — pair a
  destructive-command guard with `permissions.deny`, not `if` alone.
- **A hook can't hard-block over HTTP with just a status code.** Return 2xx + a JSON decision body.

> Source: https://code.claude.com/docs/en/hooks · https://code.claude.com/docs/en/plugins-reference · https://code.claude.com/docs/en/settings · reviewed against Claude Code 2.1.218 · 2026-07-23
