"""Pure fail-closed acceptance matrix across independent KLONE domains."""
from __future__ import annotations

DOMAINS = (
    "hypervisor", "permissions", "audit", "memory", "cognition",
    "research", "genomics", "media", "simulation", "android",
    "ci", "deployment",
)
STATES = frozenset({"passed", "failed", "pending", "unverified", "not_applicable"})


def summarize_acceptance(results: dict[str, str]) -> dict:
    if not isinstance(results, dict) or set(results) != set(DOMAINS):
        raise ValueError("all acceptance domains must be explicitly represented")
    if any(type(state) is not str or state not in STATES for state in results.values()):
        raise ValueError("invalid acceptance state")
    passed = sorted(name for name, state in results.items() if state == "passed")
    blocked = sorted(name for name, state in results.items() if state != "passed")
    return {
        "domains": dict(results),
        "passed_count": len(passed),
        "total_count": len(DOMAINS),
        "blocked_domains": blocked,
        "all_checks_passed": not blocked,
        "deployment_approval": False,
        "manual_review_required": True,
    }
