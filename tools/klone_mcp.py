"""Optional local MCP interface for the KLONE GitHub/Termux bridge.

Run with: python -m pip install mcp
Then: python tools/klone_mcp.py
This is a LOCAL stdio MCP server, not an automatically registered ChatGPT plugin.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.request

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit("Install optional dependency: python -m pip install mcp") from exc

mcp = FastMCP("KLONE Termux Bridge")
REPO = os.environ.get("KLONE_GITHUB_REPO", "SickDinner/klone")
ROOT = Path(os.environ.get("KLONE_ROOT", str(Path.home() / "klone-next"))).resolve()
ALLOWED = ("status", "git_status", "tests", "health")


def github(method, path, payload=None):
    token = os.environ.get("KLONE_GITHUB_TOKEN")
    if not token:
        raise ValueError("KLONE_GITHUB_TOKEN missing")
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        "https://api.github.com" + path, method=method, data=data,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "klone-mcp",
                 **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


@mcp.tool()
def bridge_capabilities() -> dict:
    """Describe the safe, allowlisted operations available to the Termux agent."""
    return {"repository": REPO, "actions": list(ALLOWED),
            "transport": "GitHub issues; local Termux agent must be running",
            "arbitrary_shell": False}


@mcp.tool()
def queue_termux_action(action: str) -> dict:
    """Queue one approved action as a GitHub issue; does not execute directly."""
    if action not in ALLOWED:
        raise ValueError("Action not allowlisted")
    return github("POST", f"/repos/{REPO}/issues",
                  {"title": f"KLONE Termux: {action}",
                   "body": json.dumps({"action": action}),
                   "labels": ["klone-termux-task"]})


@mcp.tool()
def read_termux_task(issue_number: int) -> dict:
    """Read task status and agent replies from GitHub."""
    if issue_number < 1:
        raise ValueError("Invalid issue number")
    issue = github("GET", f"/repos/{REPO}/issues/{issue_number}")
    comments = github("GET", f"/repos/{REPO}/issues/{issue_number}/comments?per_page=30")
    return {"number": issue_number, "title": issue["title"],
            "state": issue["state"],
            "comments": [{"author": c["user"]["login"], "body": c["body"]}
                         for c in comments]}


if __name__ == "__main__":
    mcp.run(transport="stdio")
