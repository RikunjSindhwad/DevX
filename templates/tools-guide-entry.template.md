<!--
TOOLS-GUIDE ENTRY TEMPLATE — use this for a concrete tool guide under tools-guide/.
Goal: teach an agent how to choose, run, and interpret a tool without cargo-culting commands.
Keep it short, current, and specific to one tool or tightly-coupled tool pair.
-->

# {tool name} — {job it does}

## When to use
- {Use case / project signal that calls for this tool}
- {When another tool is a better fit}

## Commands
| Need | Command | Notes |
|---|---|---|
| Install / ensure | `{command}` | {safe install scope, lockfile impact} |
| Run all | `{command}` | {expected working dir} |
| Run focused | `{command}` | {how to filter to one file/test/package} |
| Fix/format | `{command}` | {whether it mutates files} |

## Interpret failures
- {Common failure shape} → {likely cause} → {next diagnostic command}
- {Common failure shape} → {likely cause} → {next diagnostic command}

## Safety
- Never run `{dangerous command}` because {why}.
- Before adding/changing dependencies, check {lockfile/advisory command}.

## Verification
- A clean run looks like: `{summary line or status}`.
- If skipped, record why in the handoff Verification section.
