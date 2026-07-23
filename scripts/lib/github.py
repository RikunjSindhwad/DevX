"""GitHub code/repo search via the `gh` CLI — native tools can't do code search."""
from __future__ import annotations

import json
import os
import shutil
import subprocess


def cmd_github_search(args) -> dict:
    gh = shutil.which("gh")
    if not gh:
        return {"ok": False, "error": "gh CLI not found",
                "hint": "install gh and `gh auth login`, or set the github_token userConfig."}
    # map the userConfig github_token into gh's environment (H-01) without clobbering an existing login
    env = os.environ.copy()
    tok = os.environ.get("CLAUDE_PLUGIN_OPTION_GITHUB_TOKEN")
    if tok and not env.get("GH_TOKEN") and not env.get("GITHUB_TOKEN"):
        env["GH_TOKEN"] = tok
    fields = ("repository,path,url,textMatches" if args.kind == "code"
              else "fullName,url,description,stargazersCount")
    cmd = [gh, "search", args.kind, args.query, "--limit", str(args.limit), "--json", fields]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=40, env=env)
        data = json.loads(proc.stdout or "[]")
        return {"ok": proc.returncode == 0, "kind": args.kind, "count": len(data),
                "results": data, "stderr": proc.stderr.strip() or None}
    except Exception as e:
        return {"ok": False, "error": str(e)}
