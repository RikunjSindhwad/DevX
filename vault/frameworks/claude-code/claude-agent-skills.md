---
id: claude-agent-skills
title: Authoring Agent Skills (SKILL.md)
type: framework
tags: [claude-code, agent-skills, skill-md, progressive-disclosure, frontmatter, description, tools, prompt-engineering, commands]
summary: How to write an Agent Skill — the SKILL.md frontmatter, progressive disclosure (lazy-loading body and bundled files), and crafting a description that triggers the skill at the right time.
related:
  - {slug: claude-code-plugins, rel: relates-to}
  - {slug: prompt-engineering-for-claude, rel: relates-to}
  - {slug: writing-claude-subagents, rel: relates-to}
created: 2026-06-21
---

# Authoring Agent Skills (SKILL.md)

An Agent Skill is a reusable, filesystem-based capability: a folder with a `SKILL.md` file plus optional bundled scripts, templates, and reference documents. Skills load on demand — Claude knows a skill exists from its lightweight metadata, and pulls the full instructions only when a request matches. This keeps the base context small while letting you package arbitrarily deep domain knowledge. Create a skill when you keep pasting the same instructions into chat, or when a section of your persistent context file has grown into a procedure rather than a fact.

## What a Skill Is

A skill directory follows this layout:

```
my-skill/
├── SKILL.md          # required — main instructions and frontmatter
├── reference.md      # optional — detail loaded only when referenced
├── examples.md       # optional — usage examples
└── scripts/
    └── helper.py     # optional — executed via bash; output enters context
```

The `SKILL.md` file is the single required entrypoint. Everything else is optional supporting material. Claude navigates this structure like filesystem directories, reading files only when it needs them.

Skills share a filesystem packaging model across supported Claude surfaces, but discovery,
frontmatter, tool permissions, execution environment, and distribution are surface-specific. Validate
against the target surface rather than assuming identical behavior.

**Custom commands and skills share an invocation surface but are not interchangeable schemas.**
Claude Code continues to discover legacy `.claude/commands/*.md` files, while
`.claude/skills/<name>/SKILL.md` supports bundled resources and skill-specific fields. Prefer the
skills directory for new capabilities. Every Markdown file under `commands/` is discoverable as a
command, so do not place `README.md` or other prose there unless it is intended to be invoked.

## SKILL.md Frontmatter

Every `SKILL.md` starts with a YAML block between `---` markers. The two fields that matter most:

```yaml
---
name: processing-pdfs
description: Extract text and tables from PDF files, fill forms, merge documents.
  Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
---
```

**`name`** (optional in Claude Code; required via the API)
- Display label shown in skill listings. In Claude Code the command name comes from the *directory name*, not this field — except for a plugin-root `SKILL.md`, where `name` does set the command.
- Follow the current target surface's validator for length and character restrictions; these constraints
  are versioned and are not identical across every skill surface.

**`description`** (recommended; required via the API)
- This is the primary discovery signal Claude uses to decide whether to invoke the skill. The body and
  bundled files load only after the skill is selected.
- Keep it comfortably within the current surface's documented limit; do not rely on a copied
  cross-surface character count.
- Prefer capability-focused third-person phrasing ("Processes Excel files…") that reads cleanly in a
  catalog.
- State **what** the skill does and **when** to use it, including specific trigger words and request patterns.
- Put the highest-signal content first — the listing truncates at the character cap, so front-load the most discriminating phrases.

Other useful frontmatter fields (Claude Code):

| Field | Purpose |
|---|---|
| `disable-model-invocation: true` | User-only invocation — Claude cannot trigger automatically; removes description from context |
| `user-invocable: false` | Claude-only invocation — hides skill from `/` menu |
| `allowed-tools` | Matching tools preapproved for the skill invocation; does not restrict all other tools |
| `disallowed-tools` | Tools prohibited while the skill is active; use this when a restriction is required |
| `context: fork` | Runs the skill in an isolated subagent context |
| `agent` | Which subagent type to use with `context: fork` (e.g., `Explore`, `Plan`) |

## Writing a High-Signal Description

The description decides invocation. A weak description causes the skill to miss its triggers or fire on irrelevant requests. Rules from the official best-practices guide:

1. **Use catalog-style phrasing.** Third-person capability language is concise and works well in skill
   listings.
2. **Include trigger words.** Think about the exact words a user would say. Include them literally.
3. **State when, not just what.** "Use when the user asks for help writing commit messages or reviewing staged changes" is far more useful than "Generates commit messages."
4. **One capability per skill.** A description that covers too many actions loses precision. Split complex workflows into focused skills.
5. **Avoid vague descriptions.** `Helps with documents` tells Claude nothing. `Extracts text and tables from PDF files, fills forms, merges documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.` gives Claude enough to pick this skill over 100 others.
6. **Put key terms first.** Hosts have finite discovery budgets and may truncate long metadata; keep the
   discriminating capability and trigger terms near the start.

## Progressive Disclosure — Three Loading Levels

Skills are designed around progressive disclosure: information enters the context window only when needed.

| Level | Content | When Loaded | Cost characteristic |
|---|---|---|---|
| 1 — Metadata | `name` + `description` from YAML frontmatter | During discovery | Small but cumulative |
| 2 — Instructions | `SKILL.md` body (the markdown below the frontmatter) | When the skill is triggered | Counts against active context |
| 3 — Resources | Bundled files and scripts referenced from `SKILL.md` | When read or executed | Pay only for material/results loaded |

**Why this matters for token economy:** metadata from many installed skills accumulates, while full
instructions and supporting files are loaded on demand. A script's source need not enter context when
executed, but its output does.

Practical consequences:
- Keep `SKILL.md` concise enough to load as a coherent procedure. Move optional detail to named
  supporting files linked from the body.
- Write instructions for the duration and scope the target host documents; do not rely on undocumented
  assumptions about how long injected content survives compaction.
- Keep resource routing shallow and explicit. Add navigation when a supporting file is long enough that
  selective reading is useful.

## Authoring Practice

**One skill = one capability.** Keep scope tight. A skill that covers deployment, commit generation, and code review all at once will have a weak description and confused invocation.

**Body stays skimmable.** Use headings, short paragraphs, and code examples. Claude is already smart — only add context it doesn't already have. Challenge every paragraph: "Does this justify its token cost once the skill is in context?"

**Put long reference material in bundled files.** API specifications, database schemas, extensive examples — these belong in separate files that Claude reads only when the task requires them. Reference them from `SKILL.md` with a brief label so Claude knows what each file contains and when to reach for it.

**Make scripts deterministic.** Scripts bundled in `scripts/` can be executed without first copying
their full source into the prompt, while their output and any explicitly read source can enter context.
Scripts are the right tool for repeatable validation or structured transformations. Use
`${CLAUDE_SKILL_DIR}` to reference bundled scripts portably when the target host supports it.

**Do not put secrets in a skill.** Skills are checked into version control or uploaded to shared workspaces. Credentials, API keys, and tokens belong in environment variables, not in `SKILL.md` or bundled files. See [[auth-and-secrets]] for patterns.

**Control invocation mode deliberately.** Deployments, commits, and any operation with side effects should have `disable-model-invocation: true` — you don't want Claude deciding to deploy because the code looks ready. Background reference knowledge that isn't a user-facing command should use `user-invocable: false`.

**Evaluate before shipping.** Collect realistic positive and negative trigger prompts, run them in
fresh sessions with and without the skill, and compare invocation and output quality. Record the tested
Claude Code version.

## Surfaces

Skills use the same `SKILL.md` authoring model across all Claude surfaces. The runtime and sharing scope differ:

| Surface | Skill discovery | Sharing scope | Network access |
|---|---|---|---|
| **Claude Code** | Filesystem-based (`~/.claude/skills/`, `.claude/skills/`, plugin `skills/`); discovered automatically | Personal (user), project, or plugin | Governed by host permissions, sandbox, and tool policy |
| **Claude API** | API-managed skill/container integration; consult current API docs for headers and fields | Workspace/account policy | Container policy |
| **claude.ai** | Product UI and administrator capabilities | Product/workspace policy | Product/admin policy |

**Custom Skills do not sync across surfaces.** A skill uploaded to the API is not available in Claude Code or claude.ai, and vice versa. Manage them separately per surface.

## Troubleshooting

**Skill not triggering:** Verify the description includes the exact words a user would naturally use. Run `/doctor` (Claude Code) to check how many skill descriptions are being truncated or dropped due to the context budget. Try invoking directly with `/skill-name` to confirm the skill loads correctly.

**Skill triggers too often:** Make the description narrower and more specific. Use `disable-model-invocation: true` if the skill should only be invoked by the user.

**Descriptions cut short or skills missing:** Use `/doctor` and the current skill documentation to
inspect discovery/budget behavior. Keep descriptions concise and put discriminating trigger phrases
first; do not depend on undocumented budget percentages or internal setting names.

> Source: https://code.claude.com/docs/en/skills · https://code.claude.com/docs/en/slash-commands · reviewed against Claude Code 2.1.218 · 2026-07-23
