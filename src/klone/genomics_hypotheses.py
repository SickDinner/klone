"""Conservative, auditable hypothesis evidence bookkeeping.

This is NOT Bayesian inference, a calibrated probability, population genetic
analysis, ancestry assignment or an automated historical truth judgment.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_ref: str
    hypothesis_id: str
    stance: str
    quality: str
    rationale: str
    dependency_group: str


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str


def evaluate_hypotheses(
    hypotheses: tuple[Hypothesis, ...], evidence: tuple[EvidenceItem, ...],
) -> dict[str, object]:
    """Group source-backed evidence, deduplicate dependencies, refuse ranking."""
    if not isinstance(hypotheses, tuple) or not isinstance(evidence, tuple):
        raise ValueError("Expected immutable tuples")
    if len(hypotheses) > 100 or len(evidence) > 5000:
        raise ValueError("Input exceeds bounded analysis limit")
    ids = set()
    for h in hypotheses:
        if not isinstance(h, Hypothesis) or not isinstance(h.hypothesis_id, str) or not h.hypothesis_id.strip() or len(h.hypothesis_id) > 128:
            raise ValueError("Invalid hypothesis")
        if not isinstance(h.statement, str) or not h.statement.strip() or len(h.statement) > 4000:
            raise ValueError("Invalid hypothesis statement")
        if h.hypothesis_id in ids:
            raise ValueError("Duplicate hypothesis identifier")
        ids.add(h.hypothesis_id)
    seen = set()
    buckets = {h.hypothesis_id: {"supports": set(), "contradicts": set(), "uncertain": set()} for h in hypotheses}
    for item in evidence:
        if not isinstance(item, EvidenceItem):
            raise ValueError("Invalid evidence")
        for name in ("evidence_id", "source_ref", "rationale", "dependency_group"):
            value = getattr(item, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1000:
                raise ValueError("Invalid evidence field: " + name)
        if item.evidence_id in seen:
            raise ValueError("Duplicate evidence identifier")
        seen.add(item.evidence_id)
        if item.hypothesis_id not in ids:
            raise ValueError("Unknown hypothesis reference")
        if item.stance not in ("supports", "contradicts", "uncertain"):
            raise ValueError("Invalid evidence stance")
        if item.quality not in ("low", "medium", "high", "unknown"):
            raise ValueError("Invalid evidence quality")
        buckets[item.hypothesis_id][item.stance].add(item.dependency_group)
    results = tuple({
        "hypothesis_id": h.hypothesis_id,
        "statement": h.statement,
        "support_groups": len(buckets[h.hypothesis_id]["supports"]),
        "contradiction_groups": len(buckets[h.hypothesis_id]["contradicts"]),
        "uncertain_groups": len(buckets[h.hypothesis_id]["uncertain"]),
        "conclusion": "insufficient_for_probability_or_causal_claim",
    } for h in sorted(hypotheses, key=lambda h: h.hypothesis_id))
    canonical = json.dumps(
        {"hypotheses": [(h.hypothesis_id, h.statement) for h in sorted(hypotheses, key=lambda h: h.hypothesis_id)],
         "evidence": sorted([(e.evidence_id, e.source_ref, e.hypothesis_id, e.stance,
                              e.quality, e.rationale, e.dependency_group) for e in evidence])},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    return {"results": results, "evidence_count": len(evidence),
            "dependency_warning": "groups are not statistically independent by default",
            "fingerprint": sha256(canonical.encode("utf-8")).hexdigest()}
