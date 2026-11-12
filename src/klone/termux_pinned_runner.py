"""Bounded local test execution with Git checkout consistency checks.

Local checkout metadata is not cryptographic device attestation.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

from .termux_checkout_manifest import checkout_manifest


def run_pinned_tests(root: str | Path, *, timeout: int = 180) -> dict:
    root = Path(root).resolve()
    if not (root / "pyproject.toml").is_file():
        raise ValueError("not a KLONE checkout")
    python = root / ".venv" / "bin" / "python"
    if not python.is_file():
        raise ValueError("missing virtualenv Python")
    before = checkout_manifest(root)
    if before["dirty"]:
        return {"status": "rejected_dirty_checkout", "exit_code": None,
                "before": before, "after": None, "output": ""}
    try:
        process = subprocess.run(
            [str(python), "-m", "unittest", "discover", "-s", "tests"],
            cwd=root, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        exit_code = process.returncode
        output = (process.stdout + "\n" + process.stderr)[-5000:]
    except subprocess.TimeoutExpired:
        exit_code, output = 124, "test run timed out"
    after = checkout_manifest(root)
    stable = before["commit"] == after["commit"] and not after["dirty"]
    return {
        "status": ("passed" if exit_code == 0 and stable else
                   "rejected_checkout_changed" if not stable else "failed"),
        "exit_code": exit_code,
        "before": before,
        "after": after,
        "output": output,
        "device_identity_verified": False,
    }
