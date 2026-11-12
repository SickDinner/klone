"""KLONE Termux bridge: narrowly scoped GitHub issue task runner.

Requires KLONE_GITHUB_TOKEN (fine-grained Issues read/write) and
KLONE_TRUSTED_ACTOR (GitHub login). No shell commands from issue bodies.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.environ.get("KLONE_GITHUB_REPO", "SickDinner/klone")
ROOT = Path(os.environ.get("KLONE_ROOT", str(Path.home() / "klone-next"))).resolve()
STATE = Path(os.environ.get("KLONE_BRIDGE_STATE", str(Path.home() / ".klone-bridge-state.json")))
API = "https://api.github.com"
ALLOWED = {"status", "tests", "health", "git_status"}
LABEL = "klone-termux-task"


def api(method: str, path: str, payload=None):
    token = os.environ.get("KLONE_GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("KLONE_GITHUB_TOKEN is required")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "klone-termux-bridge",
                 **({"Content-Type": "application/json"} if data else {})},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def run_action(action: str):
    if action not in ALLOWED:
        raise ValueError("unsupported action")
    if not (ROOT / "pyproject.toml").is_file():
        raise RuntimeError("KLONE_ROOT is not a KLONE checkout")
    if action == "status":
        cmd = ["git", "rev-parse", "--short", "HEAD"]
    elif action == "git_status":
        cmd = ["git", "status", "--short"]
    elif action == "tests":
        python = ROOT / ".venv" / "bin" / "python"
        if not python.is_file():
            raise RuntimeError("KLONE .venv Python missing")
        cmd = [str(python), "-m", "unittest", "discover", "-s", "tests"]
    else:
        python = ROOT / ".venv" / "bin" / "python"
        if not python.is_file():
            raise RuntimeError("KLONE .venv Python missing")
        cmd = [str(python), "tools/local_deploy.py", "healthcheck"]
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                timeout=180 if action == "tests" else 15, check=False)
        return {"exit_code": result.returncode,
                "output": (result.stdout + "\n" + result.stderr)[-5000:]}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "output": "action timed out"}


def load_state():
    try:
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return set()


def save_state(done):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(done)), encoding="utf-8")
    tmp.replace(STATE)
    try:
        STATE.chmod(0o600)
    except OSError:
        pass


def format_result(action: str, result: dict) -> str:
    """Create a bounded, readable issue comment without leaking the API token."""
    output = str(result["output"])
    token = os.environ.get("KLONE_GITHUB_TOKEN", "")
    if token:
        output = output.replace(token, "[REDACTED]")
    summary = ""
    if action == "tests":
        match = re.search(r"Ran (\d+) tests? in ([\d.]+)s", output)
        verdict = re.search(r"^(OK(?: \(skipped=\d+\))?|FAILED \(.*\))$", output, re.MULTILINE)
        if match:
            summary = f"Tests: {match.group(1)} in {match.group(2)}s"
            if verdict:
                summary += f"; {verdict.group(1)}"
            summary += "\n\n"
    fence = chr(96) * 3
    return ("KLONE Termux bridge result for " + chr(96) + action + chr(96) + "\n\n"
            + summary + fence + "text\n" + output.replace(fence, "[fence]")[-5000:]
            + "\n" + fence + "\nExit code: " + str(result["exit_code"]))


def once():
    trusted = os.environ.get("KLONE_TRUSTED_ACTOR", "").strip()
    if not trusted:
        raise RuntimeError("KLONE_TRUSTED_ACTOR is required")
    done = load_state()
    issues = api("GET", f"/repos/{REPO}/issues?state=open&labels={LABEL}&per_page=30")
    for issue in issues:
        if "pull_request" in issue or issue["user"]["login"].lower() != trusted.lower():
            continue
        number = issue["number"]
        key = f"{REPO}#{number}"
        if key in done:
            continue
        try:
            request = json.loads(issue.get("body") or "")
            if not isinstance(request, dict) or set(request) != {"action"}:
                continue
            action = request["action"]
            if not isinstance(action, str) or action not in ALLOWED:
                continue
        except (ValueError, TypeError):
            continue
        # Mark before execution to prevent accidental repeated runs after a crash.
        done.add(key)
        save_state(done)
        try:
            result = run_action(action)
        except Exception as exc:
            result = {"exit_code": 1, "output": f"{type(exc).__name__}: {exc}"}
        message = format_result(action, result)
        api("POST", f"/repos/{REPO}/issues/{number}/comments", {"body": message})
        print(f"Completed issue #{number}: {action} exit={result['exit_code']}")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"once", "watch"}:
        print("Usage: python tools/termux_bridge.py once|watch", file=sys.stderr)
        return 2
    if sys.argv[1] == "once":
        once()
        return 0
    while True:
        try:
            once()
        except (RuntimeError, urllib.error.URLError) as exc:
            print(f"Bridge poll error: {exc}", file=sys.stderr)
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
