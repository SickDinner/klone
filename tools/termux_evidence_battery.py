"""Offline Termux battery: capture checkout provenance before and after tests.

Never changes git branches, downloads dependencies or approves deployment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def checkout(root: Path) -> dict:
    return {"commit": git(root, "rev-parse", "HEAD"),
            "branch": git(root, "branch", "--show-current"),
            "dirty": bool(git(root, "status", "--porcelain"))}


def run_battery(root: Path, output: Path, timeout: int = 240) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    before = checkout(root)
    started = datetime.now(timezone.utc).isoformat()
    python = root / ".venv" / "bin" / "python"
    if not python.is_file():
        raise FileNotFoundError(str(python))
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    commands = [
        ("syntax", [str(python), "-m", "compileall", "-q", "src/klone"]),
        ("cognition", [str(python), "-m", "unittest", "discover",
                       "-s", "tests", "-p", "test_cognition*.py", "-v"]),
        ("full", [str(python), "-m", "pytest", "-q"]),
        ("local_deploy", [str(python), "-m", "pytest", "-q",
                          "tests/test_local_deploy.py"]),
    ]
    torch_demo = root / "scripts" / "klone-local-torch-demo.py"
    stages = {}
    for name, command in commands:
        try:
            completed = subprocess.run(command, cwd=root, env=env,
                                       capture_output=True, text=True,
                                       timeout=timeout, check=False)
            code = completed.returncode
            output_text = completed.stdout + completed.stderr
        except subprocess.TimeoutExpired:
            code, output_text = 124, "Timed out"
        (output / (name + ".log")).write_text(output_text, encoding="utf-8")
        stages[name] = {"exit_code": code, "status": "passed" if code == 0 else "failed"}
    if torch_demo.is_file():
        try:
            completed = subprocess.run([str(python), str(torch_demo)], cwd=root,
                                       env=env, capture_output=True, text=True,
                                       timeout=timeout, check=False)
            code = completed.returncode
            output_text = completed.stdout + completed.stderr
            # The demo explicitly reports unavailable if torch is not installed.
            optional_status = "unavailable" if '"status": "unavailable"' in output_text else (
                "passed" if code == 0 else "failed")
        except subprocess.TimeoutExpired:
            code, output_text, optional_status = 124, "Timed out", "failed"
        (output / "torch_probe.log").write_text(output_text, encoding="utf-8")
        stages["torch_probe"] = {"exit_code": code, "status": optional_status}
    else:
        stages["torch_probe"] = {"exit_code": None, "status": "not_present"}
        (output / "torch_probe.log").write_text(
            "Optional torch demo not present in this checkout", encoding="utf-8")
    after = checkout(root)
    required_ok = all(stages[name]["status"] == "passed" for name, _ in commands)
    consistent = before["commit"] == after["commit"] and not before["dirty"] and not after["dirty"]
    report = {
        "schema_version": 1, "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "before": before, "after": after, "stages": stages,
        "required_tests_passed": required_ok,
        "checkout_consistent": consistent,
        "overall": "passed" if required_ok and consistent else "failed",
        "device_identity_verified": False, "deployment_approval": False,
    }
    (output / "run.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "klone-next")
    parser.add_argument("--output", "--output-dir", dest="output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args(argv)
    if args.timeout < 1 or args.timeout > 3600:
        parser.error("timeout must be 1..3600")
    report = run_battery(args.root.resolve(), args.output.resolve(), args.timeout)
    print(json.dumps(report, indent=2))
    return 0 if report["overall"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
