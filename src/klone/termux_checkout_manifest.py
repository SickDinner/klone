"""Read-only local checkout metadata for Termux bridge evidence."""
from __future__ import annotations

import subprocess
from pathlib import Path


def checkout_manifest(root: str | Path) -> dict:
    root = Path(root).resolve()

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True,
            text=True, timeout=10, check=True,
        )
        return result.stdout.strip()

    commit = git("rev-parse", "HEAD")
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("invalid checkout commit SHA")
    dirty = bool(git("status", "--porcelain"))
    return {
        "commit": commit,
        "dirty": dirty,
        "source": "local_git_checkout",
        "device_identity_verified": False,
        "execution_attested": False,
    }
