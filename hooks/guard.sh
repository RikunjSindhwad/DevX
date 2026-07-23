#!/usr/bin/env bash
# Thin PreToolUse safety NET (not a policy engine — see ARCHITECTURE.md anti-goals).
# Blocks only a tiny denylist of catastrophic, hard-to-undo Bash commands at the
# main/orchestrator level. Real per-agent safety comes from tight tool allowlists;
# real VCS safety comes from the git agent's operator gates.
#
# Reads the tool-call JSON on stdin; blocks by emitting a PreToolUse deny decision.
set -euo pipefail
payload="$(cat 2>/dev/null || true)"
cmd="$(printf '%s' "$payload" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 || true)"

block() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}\n' "\"$1\""
  exit 0
}

# rm -rf on / or $HOME, disk wipes, fork bombs, curl|sh, and force history ops.
case "$cmd" in
  *"rm -rf /"*|*"rm -rf /*"*|*'rm -rf ~'*|*'rm -rf $HOME'*) block "Refused: recursive force-delete of a root/home path." ;;
  *"find "*"-delete"*)                                       block "Refused: find … -delete can mass-delete (e.g. find / -delete)." ;;
  *"chmod -R 000"*|*"chmod 000 /"*)                          block "Refused: chmod that strips all permissions off a root path." ;;
  *"mkfs"*|*"dd if="*"of=/dev/"*|*"> /dev/sd"*|*"of=/dev/sd"*) block "Refused: destructive disk / block-device operation." ;;
  *":(){ :|:& };:"*)                                          block "Refused: fork bomb." ;;
  *"curl "*"| sh"*|*"wget "*"| sh"*|*"curl "*"| bash"*)       block "Refused: piping a remote script straight into a shell." ;;
  *"git push --force"*|*"git push -f"*|*"git push "*" +"*|*"git push "*"+refs/"*|*"git push "*"+HEAD:"*|*"reset --hard"*|*"git branch -D"*|*"git update-ref -d"*) block "Refused here: destructive git op must go through the git agent's operator gate." ;;
esac
exit 0
