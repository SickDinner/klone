"""Explainable, deterministic next-task ranking for KLONE engineering.

Risk scores are transparent heuristics, not learned probabilities.
"""
from __future__ import annotations

from collections.abc import Mapping

from .acceptance_matrix import DOMAINS

IMPACT = {
    "hypervisor": 5, "permissions": 5, "audit": 5, "memory": 5,
    "cognition": 3, "research": 3, "genomics": 4, "media": 2,
    "simulation": 2, "android": 5, "ci": 5, "deployment": 5,
}
STATUS_WEIGHT = {
    "failed": 5, "unverified": 3, "pending": 2,
    "not_applicable": 1, "passed": 0,
}


def prioritize_quality_work(domain_states: Mapping[str, str]) -> list[dict]:
    if not isinstance(domain_states, Mapping) or set(domain_states) != set(DOMAINS):
        raise ValueError("all domains required")
    if any(type(state) is not str or state not in STATUS_WEIGHT
           for state in domain_states.values()):
        raise ValueError("invalid domain state")
    tasks = [
        {
            "domain": domain,
            "state": domain_states[domain],
            "priority_score": IMPACT[domain] * STATUS_WEIGHT[domain_states[domain]],
            "reason": "impact x unresolved-status weight",
            "recommended_action": (
                "repair failing regression" if domain_states[domain] == "failed"
                else "collect independently checkable evidence"
                if domain_states[domain] in {"unverified", "pending"}
                else "review applicability"
            ),
        }
        for domain in DOMAINS if domain_states[domain] != "passed"
    ]
    return sorted(tasks, key=lambda task: (-task["priority_score"], task["domain"]))
