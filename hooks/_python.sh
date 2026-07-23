#!/usr/bin/env bash
# Resolve a Python interpreter for DevX plugin hooks. Hook scripts are stdlib-only, so plain
# `python3` works even before any workspace venv exists.
#
# Priority:
#   1. $DEVX_PYTHON   — operator escape hatch (an interpreter the operator vouches for)
#   2. python3 from PATH — stdlib-only fallback
#
# SECURITY: we deliberately do NOT consider <workspace>/.devx/.venv/bin/python3 here. That venv is
# git-ignored and source-writable by the implementer, so a planted interpreter there could
# hijack the security hooks (e.g. model_guard) that this runner launches. A security hook must never
# run a workspace-writable interpreter. bin/devx's own venv ladder is separate and is fine to keep.
#
# Hooks fire from the workspace cwd ($PWD = the target repo). Do NOT use $CLAUDE_PLUGIN_ROOT here —
# that's the read-only/shared plugin install dir. Keep this fast: no `uv run` in a hook hot path.
#
# Usage: _python.sh <script.py> [args...]
set -u

if [[ -n "${DEVX_PYTHON:-}" ]] && [[ -x "${DEVX_PYTHON}" ]]; then
    exec "${DEVX_PYTHON}" "$@"
fi

exec python3 "$@"
