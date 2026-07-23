# DevX prompt-behavior evaluations

These cases exercise the Markdown control plane as behavior, not prose style. Run each case in a fresh
session with the current plugin installed, using a disposable repository fixture. Do not carry chat
history or prior agent context between cases.

`cases.json` is intentionally runner-neutral. Each case contains:

- `prompt`: the operator/dispatch situation to present.
- `expected`: observable actions or durable artifacts that must occur.
- `forbidden`: behavior that fails the case.
- `evidence_files`: the canonical Markdown contracts the result should be traceable to.

## Scoring

Score each expected item `1` only when the transcript or resulting files prove it happened. Score each
forbidden item `1` only when it did **not** happen. A case passes when every expected and forbidden item
scores `1`; averages cannot hide a safety or lifecycle failure.

Record model alias/version, host version, case id, result, token/latency data when available, and the
evidence artifact. Re-run the complete set after a prompt/agent/stage change. Compare one change at a time
against the prior baseline.

The pytest suite validates corpus shape and static contract anchors. It does not pretend to execute a
model trajectory; fresh-session runs are the behavioral evidence.
