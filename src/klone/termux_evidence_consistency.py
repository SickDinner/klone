"""Fail-closed consistency gate for pinned local test reports.

No network, deployment or hardware attestation.
"""
from __future__ import annotations

from collections.abc import Mapping


def review_pinned_termux_result(report: Mapping, *, expected_commit: str) -> dict:
    if not isinstance(report, Mapping):
        raise ValueError("invalid report")
    if not isinstance(expected_commit, str) or len(expected_commit) != 40 or any(
        char not in "0123456789abcdef" for char in expected_commit
    ):
        raise ValueError("invalid expected SHA")
    before, after = report.get("before"), report.get("after")
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ValueError("missing checkout snapshots")
    if before.get("commit") != expected_commit or after.get("commit") != expected_commit:
        raise ValueError("commit mismatch")
    if before.get("dirty") is not False or after.get("dirty") is not False:
        raise ValueError("dirty checkout")
    if report.get("status") != "passed" or type(report.get("exit_code")) is not int or report["exit_code"] != 0:
        raise ValueError("test run not successful")
    if report.get("device_identity_verified") is not False:
        raise ValueError("untrusted device attestation flag")
    return {
        "commit": expected_commit,
        "local_checkout_consistency": "passed",
        "device_identity": "unverified",
        "remote_provenance": "unverified",
        "manual_review_required": True,
        "deployment_approval": False,
    }
