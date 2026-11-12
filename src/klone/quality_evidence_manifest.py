"""Deterministic, offline evidence manifests for KLONE acceptance reviews."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from .acceptance_matrix import DOMAINS


def fingerprint_evidence(*, commit: str, domain_evidence: Mapping) -> dict:
    if not isinstance(commit, str) or len(commit) != 40 or any(
        c not in "0123456789abcdef" for c in commit
    ):
        raise ValueError("invalid commit SHA")
    if not isinstance(domain_evidence, Mapping):
        raise ValueError("invalid evidence mapping")
    if set(domain_evidence) != set(DOMAINS):
        raise ValueError("every domain must be represented")
    items = {}
    for domain in DOMAINS:
        entry = domain_evidence[domain]
        if not isinstance(entry, Mapping) or set(entry) != {"state", "source", "reference"}:
            raise ValueError("invalid domain evidence entry")
        state, source, reference = entry["state"], entry["source"], entry["reference"]
        if state not in {"passed", "failed", "pending", "unverified", "not_applicable"}:
            raise ValueError("invalid state")
        if not isinstance(source, str) or not isinstance(reference, str):
            raise ValueError("invalid provenance")
        if state == "passed" and (not source.strip() or not reference.strip()):
            raise ValueError("passed domain requires source and reference")
        items[domain] = {"state": state, "source": source, "reference": reference}
    payload = {"schema_version": 1, "commit": commit, "domains": items}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True).encode("utf-8")
    return {**payload, "sha256": hashlib.sha256(serialized).hexdigest(),
            "authenticated": False, "deployment_approval": False}
