---
id: prompt-engineering-for-claude
title: Prompt Engineering for Claude
type: framework
tags: [claude, prompt-engineering, xml-tags, examples, system-prompt, evaluation, tool-instructions]
summary: Durable prompting practices for Claude — clear task contracts, structured context, representative examples, explicit tool triggers, observable checks, and version-aware API guidance.
related:
  - {slug: claude-agent-skills, rel: relates-to}
  - {slug: writing-claude-subagents, rel: relates-to}
  - {slug: problem-solving-techniques, rel: see-also}
created: 2026-06-21
---

# Prompt Engineering for Claude

Claude model names, feature flags, and prompting behavior evolve. This entry keeps the durable
techniques—clear instructions, structured context, representative examples, explicit tool triggers,
and evaluation—and marks model/API details as items to verify against current official docs.

## Be Clear and Direct

Claude responds well to explicit, specific instructions. Vague prompts produce vague results. Think of Claude as a capable new colleague who lacks context on your norms and workflows: give it the goal, the format, and the constraints.

Practical heuristics:
- State the desired output format and any length or style constraints up front.
- When order or completeness matters, provide steps as a numbered list.
- Add context on *why* a behavior is important — Claude generalizes from the explanation and tends to produce more targeted responses.
- Golden rule: show the prompt to a colleague with minimal context. If they would be confused, Claude will be too.

Avoid relying on the model to infer intent from indirect phrasing. If you want above-and-beyond behavior, request it explicitly.

## Structure Prompts with XML Tags

XML tags help Claude parse complex prompts unambiguously when a prompt mixes instructions, context, examples, and variable inputs. Wrapping each type of content in its own tag (e.g., `<instructions>`, `<context>`, `<input>`) reduces misinterpretation.

Best practices:
- Use consistent, descriptive tag names across all your prompts.
- Nest tags when content has a natural hierarchy (e.g., `<documents>` containing multiple `<document index="n">` children).
- Reference tags by name in the instructions so the model knows what to look at ("Summarize the text in `<document>`").
- Use `<example>` / `<examples>` to wrap few-shot examples; this lets Claude distinguish them from live instructions.

## Examples (Multishot Prompting)

Examples are one of the highest-leverage levers available. A few well-chosen examples (also called few-shot or multishot prompting) can dramatically improve output accuracy, tone, and structure — often more reliably than lengthy prose instructions alone.

When constructing examples:
- **Relevant**: mirror your actual use case closely.
- **Diverse**: cover edge cases and vary enough that the model does not pick up unintended patterns.
- **Structured**: wrap examples in `<example>` tags (or `<examples>` for a set) so Claude can reliably separate them from instructions.

Use the smallest representative set that covers normal and boundary behavior, then evaluate whether
each example improves the target metric rather than relying on a fixed count.

## Ask for observable reasoning products

For hard tasks, ask for artifacts that make the result checkable: assumptions, a short approach,
calculations, citations, tests run, or a comparison against acceptance criteria. Do not require hidden
chain-of-thought or `<thinking>` transcripts. Thinking controls, effort values, model IDs, and token
parameters are versioned API features; select them from the current official model documentation and
measure the quality/latency/cost tradeoff.

**Self-check**: ask the model to verify the answer against explicit criteria and report the check or
evidence. This is more useful than a generic request to "think harder."

## System Prompts: Role and Durable Constraints

Set role/persona and stable constraints in the system prompt, not in the human turn. A single sentence is enough to meaningfully shift behavior:

```python
system="You are a helpful coding assistant specializing in Python."
```

Keep durable constraints stable and separate from request-specific input. If using provider prompt
caching, follow the current API's cache-boundary rules rather than assuming the entire system prompt is
always cached.

Use the system prompt to:
- Establish persona and domain focus.
- Set output format defaults (prose vs. Markdown, response length, etc.).
- Gate agentic behaviors (proactive action vs. conservative action, parallel tool calls, autonomy limits).

## Be Prescriptive About WHEN, Not Just What

For tool and skill descriptions, state the **trigger condition** explicitly — not just what the tool does, but when to call it. This measurably improves should-call rates on current models.

Example (weak): "This tool fetches current prices."
Example (strong): "Call this tool when the user asks about current prices or when a price comparison is needed to answer the question."

Re-evaluate trigger language on every model upgrade. Overly aggressive `CRITICAL`/`MUST` wording can
cause overtriggering; start with a precise `Use this tool when...` condition and measure should-call and
should-not-call behavior.

For parallel tool calling, give an explicit instruction when independent calls should run together,
then evaluate whether the model follows it:

> If you intend to call multiple tools and there are no dependencies between the calls, make all of the independent calls in parallel.

## Prefill and structured-output support are model-specific

Assistant-message prefill support is model/version-specific. Verify the current model's API
documentation; do not make prefill a portability assumption.

Common prefill use cases and their modern replacements:

| Old approach | Current replacement |
|---|---|
| Prefill `{` to force JSON | Use the model/API's documented structured-output mechanism |
| Prefill to eliminate preamble | Add `"Respond without preamble or affirmations."` to the system prompt |
| Prefill to avoid refusals | Refine the instruction; use system-prompt framing |
| Prefill to continue a generation | Prompt for continuation in the human turn |

## Agentic and Long-Context Tips

- **Long context**: place long source material before the final query/instructions when recommended by
  the current model guide, and evaluate retrieval quality on representative multi-document inputs.
- **Context budget**: design prompts and tool output for the target context limit and host compaction
  behavior; do not assume a model can see an exact remaining-token counter.
- **Subagent orchestration**: when the host/model can delegate proactively, state positive and negative
  delegation criteria so simple tasks do not incur unnecessary fan-out.
- **Self-correction chains**: generate a draft → review against criteria → refine. Each step is a separate API call so you can log, evaluate, or branch at any point.

> Source: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview · reviewed 2026-07-23
