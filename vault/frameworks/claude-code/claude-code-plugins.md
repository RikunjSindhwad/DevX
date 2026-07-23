---
id: claude-code-plugins
title: Authoring Claude Code Plugins
type: framework
tags: [claude-code, plugins, plugin-json, marketplace, commands, agents, hooks, skills, mcp, distribution]
summary: How to structure a Claude Code plugin — the plugin.json manifest, bundling commands/agents/skills/hooks/MCP servers, and distributing via a marketplace.
related:
  - {slug: claude-agent-skills, rel: relates-to}
  - {slug: writing-claude-subagents, rel: relates-to}
  - {slug: claude-code-hooks, rel: relates-to}
created: 2026-06-21
---

# Authoring Claude Code Plugins

A Claude Code plugin is a self-contained directory that bundles skills, agents, hooks, MCP servers, LSP servers, and background monitors into a single versioned, shareable unit. Plugins differ from standalone `.claude/` configuration in one key respect: components are namespaced (e.g. `/my-plugin:review` instead of `/review`), preventing conflicts when multiple plugins define identically named skills. Start with standalone configuration for local iteration; package as a plugin when you are ready to share or distribute.

## Plugin anatomy

Every plugin is a directory with a `.claude-plugin/plugin.json` manifest (a marketplace root instead
uses `.claude-plugin/marketplace.json`). Current strict validation rejects a plugin directory with
neither manifest. Components are discovered from standard locations at the plugin root.

**Manifest location and minimum shape:**

```
my-plugin/
└── .claude-plugin/
    └── plugin.json   ← only file that goes in .claude-plugin/
```

```json
{
  "name": "my-plugin",
  "description": "What this plugin does",
  "version": "1.0.0",
  "author": { "name": "Author Name" }
}
```

**Common manifest fields** (the schema evolves; strict validation is authoritative):

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | Kebab-case; becomes the skill namespace prefix |
| `displayName` | string | No | Human-readable UI label; may contain spaces; requires v2.1.143+ |
| `version` | string | No | Semantic version string. If set, updates are gated on a version bump. If omitted, the git commit SHA is used and every commit is a new version. |
| `description` | string | No | Shown in the plugin manager |
| `author` | object | No | `{ name, email, url }` |
| `homepage` | string | No | Documentation URL |
| `repository` | string | No | Source repository URL |
| `license` | string | No | SPDX identifier (e.g. `MIT`) |
| `keywords` | array | No | Discovery tags |
| `defaultEnabled` | boolean | No | `false` installs the plugin disabled; requires v2.1.154+ |
| `dependencies` | array | No | Other plugins this plugin requires, with optional semver constraints |
| `userConfig` | object | No | Operator-configurable values; validate types, sensitivity, and component substitution contexts |

Claude Code ignores unrecognized top-level fields (useful for dual-use manifests that also serve as VS Code extension manifests or npm `package.json` files), and `claude plugin validate` reports them as **warnings** that don't block — a manifest with only unrecognized-field warnings still passes. Pass `--strict` to treat those warnings as errors.

**Critical layout rule:** `commands/`, `agents/`, `skills/`, `hooks/`, and all other component directories must sit at the **plugin root**, not inside `.claude-plugin/`. Only `plugin.json` belongs inside `.claude-plugin/`.

## Standard directory layout

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json           # required plugin manifest
├── skills/                   # preferred: subdirs with SKILL.md
│   └── review/
│       └── SKILL.md
├── commands/                 # alternative: flat .md files (legacy style)
├── agents/                   # subagent markdown files
├── hooks/
│   └── hooks.json
├── .mcp.json                 # MCP server definitions
├── .lsp.json                 # LSP server configurations
├── monitors/
│   └── monitors.json         # background monitors (experimental)
├── bin/                      # executables added to Bash tool's PATH
├── settings.json             # default settings when enabled (only `agent` / `subagentStatusLine` keys)
└── scripts/                  # helper scripts referenced by hooks/MCP
```

A plugin that ships exactly one skill can place `SKILL.md` directly at the plugin root rather than using the `skills/` directory. The frontmatter `name` field in that `SKILL.md` controls the invocation name.

## What a plugin can bundle

**Skills** (`skills/` or `commands/` at plugin root)

Skills are the primary way plugins expose slash commands. Each skill is a folder containing `SKILL.md`. The folder name determines the skill name, prefixed with the plugin namespace:

```
skills/
└── code-review/
    └── SKILL.md      →  /my-plugin:code-review
```

`$ARGUMENTS` in `SKILL.md` captures text passed after the skill name. Skills can include supporting files (scripts, reference docs) alongside `SKILL.md`.

**Legacy commands and skills share the namespaced invocation surface, not an exact schema.**
`commands/deploy.md` and `skills/deploy/SKILL.md` can both produce `/my-plugin:deploy`, but skills
support their own frontmatter and bundled resources. Prefer `skills/` for new work. Every Markdown file
under `commands/` is discoverable, so a `commands/README.md` unintentionally becomes a command.

**Agents** (`agents/` at plugin root)

Plugin agents are specialized subagents Claude invokes automatically based on task context. They appear in the `/agents` interface. Agent files are markdown with YAML frontmatter:

```markdown
---
name: security-reviewer
description: Reviews code changes for security issues. Use when analyzing diffs or PRs.
model: sonnet
effort: medium
maxTurns: 20
disallowedTools: Write, Edit
---

System prompt for the agent...
```

Plugin agents use the documented plugin-agent subset of subagent frontmatter; see
[[writing-claude-subagents]] and the current plugins reference. Do not infer support from a
project-agent field or from a single UI experiment—run strict validation and a behavior probe on the
target Claude Code version.

**Hooks** (`hooks/hooks.json` at plugin root)

Plugins can respond to the lifecycle events supported by the installed Claude Code version. See
[[claude-code-hooks]] and the current reference for event/matcher/output details. A plugin's hooks
merge with user/project hooks rather than replacing them.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format-code.sh",
            "args": []
          }
        ]
      }
    ]
  }
}
```

Hook types: `command`, `http`, `mcp_tool`, `prompt`, `agent`.

**MCP servers** (`.mcp.json` at plugin root, or inline in `plugin.json`)

Plugins bundle Model Context Protocol servers that start automatically when the plugin is enabled. Use `${CLAUDE_PLUGIN_ROOT}` to reference binaries and config files bundled with the plugin. The top-level key is `mcpServers` in both places a plugin can define one — a dedicated `.mcp.json` at the plugin root, and inline via the `mcpServers` field in `plugin.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/my-server",
      "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
      "env": { "DATA_PATH": "${CLAUDE_PLUGIN_DATA}/store" }
    }
  }
}
```

**LSP servers** (`.lsp.json` at plugin root, or inline in `plugin.json`)

Provides language intelligence (diagnostics, go-to-definition, hover info). The language server binary must be installed separately; the plugin only configures the connection.

**Background monitors** (`monitors/monitors.json`, experimental)

Monitors run a shell command for the lifetime of the session and deliver every stdout line to Claude as a notification. Requires v2.1.105+.

```json
[
  {
    "name": "error-log",
    "command": "tail -F ./logs/error.log",
    "description": "Application error log"
  }
]
```

## Environment variables for file references

Three variables are substituted everywhere (skill content, agent content, hook commands, MCP/LSP configs, monitor commands) and exported to subprocesses:

| Variable | Resolves to | Use for |
|---|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | Plugin's installation directory (changes on update) | Bundled scripts, binaries, config files |
| `${CLAUDE_PLUGIN_DATA}` | Persistent state directory (survives updates) | `node_modules`, caches, generated files |
| `${CLAUDE_PROJECT_DIR}` | Project root (where Claude Code was launched) | Project-local scripts or config |

`${CLAUDE_PLUGIN_ROOT}` is version-specific/replaceable and must not hold durable state.
`${CLAUDE_PLUGIN_DATA}` is the persistent plugin-data location and is removed when the last installed
scope is uninstalled; treat uninstall as a data-lifecycle event.

## User-configurable options

The `userConfig` field in `plugin.json` prompts users for values at enable time. Sensitive values are
stored in the system keychain where supported, otherwise in Claude Code's credential storage. Each
configured value is available through the documented `${user_config.KEY}` substitution and
`CLAUDE_PLUGIN_OPTION_KEY` environment form in supported component contexts; verify scope with strict
validation/current docs.

```json
{
  "userConfig": {
    "api_token": {
      "type": "string",
      "title": "API token",
      "description": "Authentication token for the service",
      "sensitive": true,
      "required": true
    }
  }
}
```

Supported types: `string`, `number`, `boolean`, `directory`, `file`.

## Plugin installation scopes

| Scope | Settings file | Use case |
|---|---|---|
| `user` (default) | `~/.claude/settings.json` | Personal; available across all projects |
| `project` | `.claude/settings.json` | Team-shared via version control |
| `local` | `.claude/settings.local.json` | Project-specific; gitignored |

CLI: `claude plugin install my-plugin@marketplace --scope project`

## Marketplaces

A marketplace is a `marketplace.json` catalog that lists plugins and their sources. Users add a marketplace once; they can then discover, install, and update plugins from it.

**Marketplace file location and shape:**

```
my-marketplace/
└── .claude-plugin/
    └── marketplace.json
```

```json
{
  "name": "team-tools",
  "owner": { "name": "Dev Team", "email": "devtools@example.com" },
  "plugins": [
    {
      "name": "code-formatter",
      "source": "./plugins/formatter",
      "description": "Format code on save",
      "version": "2.1.0"
    },
    {
      "name": "deploy-helper",
      "source": { "source": "github", "repo": "org/deploy-plugin" },
      "description": "Deployment automation"
    }
  ]
}
```

**Marketplace schema — required fields:**

| Field | Description |
|---|---|
| `name` | Kebab-case marketplace identifier. Users reference it when installing: `plugin-name@marketplace-name`. Each user can register only one marketplace per name. |
| `owner` | Object with required `name` and optional `email`. |
| `plugins` | Array of plugin entries. |

**Optional marketplace fields:** `description`, `version`, `metadata.pluginRoot` (base directory prepended to relative sources, so entries can write `source: formatter` instead of `source: ./plugins/formatter`), `allowCrossMarketplaceDependenciesOn`.

Each entry in `plugins[]` also accepts `category` and `tags` (both purely for discovery/organization in the plugin picker) alongside any `plugin.json` field (`description`, `version`, `author`, `commands`, `hooks`, etc.) — real third-party listings in Anthropic's own curated directory set `category` and a rich `keywords`/`tags` array on every entry; first-party plugins mostly omit them since they're discovered by trust/curation rather than search.

**Plugin sources inside `marketplace.json`:**

| Type | Example source value |
|---|---|
| Relative path (same repo) | `"./plugins/my-plugin"` |
| GitHub repository | `{ "source": "github", "repo": "owner/repo", "ref": "v2.0.0", "sha": "..." }` |
| Git URL | `{ "source": "url", "url": "https://gitlab.com/team/plugin.git" }` |
| Git subdirectory | `{ "source": "git-subdir", "url": "...", "path": "tools/plugin" }` |
| npm package | `{ "source": "npm", "package": "@acme/my-plugin" }` |

When both `ref` and `sha` are set, `sha` is the effective pin.

**Adding and installing from a marketplace (user side):**

```
/plugin marketplace add ./my-marketplace         # add a local marketplace
/plugin marketplace add github:org/marketplace-repo  # add a hosted marketplace
/plugin install my-plugin@team-tools             # install a plugin from it
/plugin marketplace update                        # refresh local copy
```

CLI equivalents: `claude plugin marketplace add`, `claude plugin marketplace list`, `claude plugin marketplace update`.

**Hosting:** Push the repository containing `.claude-plugin/marketplace.json` to GitHub (recommended), GitLab, or any git host. For private distribution, host in a private repository with appropriate auth. Relative-path plugin sources only work when the marketplace is added via git — not via a direct URL to the `marketplace.json` file.

**Anthropic's public marketplaces:**

- `claude-plugins-official` — curated by Anthropic; registered automatically on first interactive launch.
- `claude-community` — the public community marketplace where third-party submissions land after review; add the repo with `/plugin marketplace add anthropics/claude-plugins-community` and install from it as `@claude-community`. Submit at `platform.claude.com/plugins/submit`.

## Patterns from real reference plugins

Observed across Anthropic's own bundled plugins (`pr-review-toolkit`, `feature-dev`, `security-guidance`, `plugin-dev`) and third-party marketplace entries (42Crunch, Airtable, wshobson/agents):

- **Many small, focused plugins beat one monolith.** Anthropic's own `claude-code-plugins` marketplace ships 12 narrow plugins rather than one do-everything plugin; a large community marketplace (wshobson/agents, 88 plugins) states the same goal explicitly: "optimized for granular installation and minimal token usage."
- **One thin orchestrator command dispatching N narrow subagents.** The command body documents which agent(s) apply to which situation and a fixed output-aggregation template; the agents themselves stay single-purpose (e.g. `pr-review-toolkit`'s `review-pr.md` dispatches 6 specialist review agents).
- **Least-privilege tool allowlists on read-only agents** — omit `Write`/`Edit`/`Bash` entirely from an investigative agent's `tools:` list rather than relying on prompt instructions alone.
- **Single-phase, composable skills over one mega-skill**, each with a narrow `description` trigger, composed into a multi-step workflow by the user or a command (e.g. separate audit/scan/setup skills rather than one "do everything" skill).
- **A shared `references/` (or `examples/`) directory one level above sibling skills**, linked by relative path from each `SKILL.md`, avoids duplicating shared material into every skill folder.
- **Explicit `AskUserQuestion` confirmation before any state-changing or live-target action**, even inside a single narrow skill — not just at the top-level command.
- **Pin third-party marketplace sources with both `ref` (human label) and `sha` (the effective pin)** — every third-party entry in Anthropic's curated directory does this.

**Anti-patterns to avoid:** mixing manual namespace-prefixing on one component type (e.g. agent names) while leaving another (e.g. skill names) unprefixed within the same plugin — pick one convention and apply it consistently; and trusting a documented JSON shape without spot-checking at least one real shipped file, since docs and shipped plugins can drift.

## Authoring practices

**Version management:** Set an explicit `version` in `plugin.json` when you want controlled rollouts — users only receive updates when you bump the field. Omit it for actively-developed internal plugins to get automatic commit-SHA versioning. Follow semantic versioning (`MAJOR.MINOR.PATCH`) for published plugins; document changes in `CHANGELOG.md`.

**Keep components focused:** Prefer smaller, purpose-built plugins over a monolithic one. Namespacing (`/plugin-name:skill`) already keeps the skill surface clean.

**The manifest is the contract:** `name` sets the namespace for all components. Changing it in a published plugin breaks existing installations. Treat it as immutable once distributed.

**Testing locally:** Use `--plugin-dir` to load a plugin without installing it. Use `/reload-plugins` to pick up changes mid-session. Pass `--plugin-dir` multiple times to load several plugins simultaneously.

**Validate before publishing:** Run `claude plugin validate ./my-plugin` before distributing. The community marketplace review pipeline runs the same check. Use `--strict` in CI to catch typos and unrecognized fields early.

**Migrating from standalone `.claude/` config:** Copy `commands/`, `agents/`, and `skills/` to the plugin root; move hooks from `settings.json` into `hooks/hooks.json`. The hook format is identical. Remove originals from `.claude/` afterward to avoid duplicates (project/user `.claude/agents/` definitions override same-named plugin agents while both coexist).

> Source: https://code.claude.com/docs/en/plugins · https://code.claude.com/docs/en/plugins-reference · https://code.claude.com/docs/en/plugin-marketplaces · reviewed against Claude Code 2.1.218 · 2026-07-23
