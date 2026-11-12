"""Normalize GitHub Actions CI manifest into KLONE evidence.

The caller must supply a manifest obtained from an independently verified
GitHub Actions artifact. This converter does not authenticate or fetch artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from .test_evidence_ledger import validate


def normalize_github_manifest(manifest: dict, *, expected_commit: str,
                              expected_run_id: str, observed_at: str | None = None) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if manifest.get("source") != "github_actions":
        raise ValueError("not a GitHub Actions manifest")
    if str(manifest.get("run_id")) != expected_run_id:
        raise ValueError("run id mismatch")
    if manifest.get("commit") != expected_commit:
        raise ValueError("commit mismatch")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    status = manifest.get("status")
    if status not in {"success", "failure", "cancelled"}:
        raise ValueError("unsupported CI result")
    os_name = manifest.get("os")
    python = manifest.get("python")
    if not isinstance(os_name, str) or not isinstance(python, str):
        raise ValueError("missing environment")
    if not os_name or not python or len(os_name) > 80 or len(python) > 30:
        raise ValueError("invalid environment")
    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    return validate({
        "source": "github_actions",
        "run_id": expected_run_id,
        "commit": expected_commit,
        "status": status,
        "observed_at": timestamp,
        "environment": f"{os_name}-py{python}",
        "details": {"run_attempt": manifest.get("run_attempt", 1)},
    })
