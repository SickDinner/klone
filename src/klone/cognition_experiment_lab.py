"""Deterministic, offline cognition experiments. No autonomous authority.

Neurochemical names are engineering metaphors, not biological simulations.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def _unit(value: object, name: str) -> float:
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise ValueError(name + " must be a number in [0,1]")
    return float(value)


def neurochemical_policy(*, dopamine: float, noradrenaline: float,
                         acetylcholine: float, inhibition: float) -> dict:
    d, n, a, i = (
        _unit(dopamine, "dopamine"),
        _unit(noradrenaline, "noradrenaline"),
        _unit(acetylcholine, "acetylcholine"),
        _unit(inhibition, "inhibition"),
    )
    novelty = round(d * (1 - i), 6)
    urgency = round(n * (1 - i / 2), 6)
    attention = round(a * (1 - i / 4), 6)
    return {
        "novelty": novelty, "urgency": urgency, "attention": attention,
        "mode": ("review" if i >= 0.8 else
                 "explore" if novelty > urgency and novelty > attention else
                 "focus" if attention >= urgency else "triage"),
        "authority": "none",
    }


def examine_claim(*, claim_id: str, supporting: list[str],
                  contradicting: list[str], independent_sources: int) -> dict:
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise ValueError("claim ID required")
    if not all(isinstance(items, list) and all(
        isinstance(x, str) and x.strip() for x in items
    ) for items in (supporting, contradicting)):
        raise ValueError("invalid evidence IDs")
    if type(independent_sources) is not int or independent_sources < 0:
        raise ValueError("invalid independent source count")
    if len(set(supporting + contradicting)) != len(supporting + contradicting):
        raise ValueError("duplicate or conflicting evidence IDs")
    return {
        "claim_id": claim_id,
        "supporting": sorted(supporting),
        "contradicting": sorted(contradicting),
        "independent_sources": independent_sources,
        "verdict": ("contested" if contradicting else
                    "unverified" if not supporting or independent_sources == 0
                    else "supported_for_review"),
        "human_review_required": True,
    }


def falsification_plan(*, hypothesis: str, metric: str,
                       reject_if_at_or_below: float,
                       observed: float | None = None) -> dict:
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        raise ValueError("hypothesis required")
    if not isinstance(metric, str) or not metric.strip():
        raise ValueError("metric required")
    threshold = _unit(reject_if_at_or_below, "threshold")
    if observed is not None:
        observed = _unit(observed, "observed")
    return {
        "hypothesis": hypothesis, "metric": metric, "fixed_rejection_threshold": threshold,
        "observed": observed,
        "outcome": ("pending" if observed is None else
                    "rejected" if observed <= threshold else "not_rejected"),
        "proves_hypothesis": False,
    }


def compare_agent_strategies(results: list[Mapping]) -> dict:
    if not isinstance(results, list) or not results:
        raise ValueError("results required")
    scored = []
    names = set()
    for item in results:
        if not isinstance(item, Mapping):
            raise ValueError("invalid strategy result")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("duplicate or invalid strategy")
        names.add(name)
        accuracy = _unit(item.get("accuracy"), "accuracy")
        hallucination = _unit(item.get("hallucination_rate"), "hallucination_rate")
        resource = _unit(item.get("resource_cost"), "resource_cost")
        scored.append({"name": name,
                       "score": round(accuracy - hallucination - resource / 4, 6)})
    return {"ranking": sorted(scored, key=lambda x: (-x["score"], x["name"])),
            "deployment_approval": False}


def council_72(votes: Mapping[int, str], *, proposal_id: str) -> dict:
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise ValueError("proposal required")
    if not isinstance(votes, Mapping) or set(votes) != set(range(1, 73)):
        raise ValueError("exactly 72 node votes required")
    if any(v not in {"yes", "no", "abstain"} for v in votes.values()):
        raise ValueError("invalid vote")
    rings = []
    for ring in range(9):
        group = [votes[i] for i in range(ring * 8 + 1, ring * 8 + 9)]
        rings.append({"ring": ring + 1, "yes": group.count("yes"),
                      "no": group.count("no"), "abstain": group.count("abstain")})
    yes = sum(r["yes"] for r in rings)
    no = sum(r["no"] for r in rings)
    payload = {"proposal_id": proposal_id, "rings": rings, "yes": yes, "no": no}
    digest = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {**payload, "fingerprint": digest,
            "advisory_consensus": yes >= 49 and no <= 16,
            "binding_authority": False, "deployment_approval": False}
