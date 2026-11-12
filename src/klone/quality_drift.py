"""Deterministic acceptance drift detection across pinned commits."""
from __future__ import annotations

from collections.abc import Mapping

from .acceptance_matrix import DOMAINS

STATES = {"passed", "failed", "pending", "unverified", "not_applicable"}


def compare_acceptance_snapshots(previous: Mapping, current: Mapping) -> dict:
    def validate(snapshot):
        if not isinstance(snapshot, Mapping):
            raise ValueError("invalid snapshot")
        commit, domains = snapshot.get("commit"), snapshot.get("domains")
        if not isinstance(commit, str) or len(commit) != 40 or any(
            c not in "0123456789abcdef" for c in commit
        ):
            raise ValueError("invalid snapshot commit")
        if not isinstance(domains, Mapping) or set(domains) != set(DOMAINS):
            raise ValueError("missing acceptance domains")
        if any(type(value) is not str or value not in STATES for value in domains.values()):
            raise ValueError("invalid acceptance state")
        return commit, domains

    old_commit, old = validate(previous)
    new_commit, new = validate(current)
    changes = [
        {"domain": domain, "before": old[domain], "after": new[domain]}
        for domain in DOMAINS if old[domain] != new[domain]
    ]
    regressions = [
        change for change in changes
        if change["before"] == "passed" and change["after"] != "passed"
    ]
    return {
        "previous_commit": old_commit,
        "current_commit": new_commit,
        "changes": changes,
        "regressions": regressions,
        "regression_count": len(regressions),
        "manual_review_required": bool(changes),
        "deployment_approval": False,
    }
