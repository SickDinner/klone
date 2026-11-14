"""72 explicit specialist profiles, deterministic deliberation and draft-only routing.

Goetic names and Dante's circles are literary design references. Affect is a
bounded numerical analogy; neither a consciousness test nor runtime authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re

from .cognition_experiment_lab import _unit, neurochemical_policy
from .cognition_core import CognitionCore
from .cognition_neurocortex import NAMES, clamp, digest
from .evidence_io import json_object, read_bounded, write_new_report

AUTHORITY = {"binding_authority": False, "external_actions": False,
             "permission_changes": False, "deployment_approval": False,
             "consciousness_claim": False}
SIGNALS = {"evidence_quality": 0.0, "uncertainty": 1.0, "risk": 0.5,
           "novelty": 0.0, "reward": 0.0, "threat": 0.0, "social_feedback": 0.0}
VOTES = {"endorse", "oppose", "defer"}
CATALOG = Path(__file__).parent / "static/council72-catalog.json"


@lru_cache(maxsize=1)
def _catalog() -> dict:
    data = json_object(read_bounded(CATALOG, 131072))
    members, rings, founders = data["members"], data["rings"], data["founder_ids"]
    if (data["schema_version"] != 1 or data["kind"] != "klone-council72-catalog" or
            len(members) != 72 or len(rings) != 9 or len(set(founders)) != 8 or
            any(type(m["id"]) is not int for m in members) or
            {m["id"] for m in members} != set(range(1, 73)) or
            {r["id"] for r in rings} != set(range(1, 10)) or data["authority"] != AUTHORITY):
        raise ValueError("invalid council catalog")
    for ring in rings:
        group = [m for m in members if m["ring"] == ring["id"]]
        if len(group) != 8 or {m["slot"] for m in group} != set(range(1, 9)) or \
                [m["id"] for m in group] != ring["member_ids"]:
            raise ValueError("invalid ring membership")
        if ring["id"] < 9 and ring["steward_id"] != founders[ring["id"] - 1]:
            raise ValueError("invalid ring steward")
    for member in members:
        if member["founder"] != (member["id"] in founders) or \
                (member["ring"] == 9) != member["founder"]:
            raise ValueError("invalid founder membership")
        if set(member["baseline_modulators"]) != set(NAMES):
            raise ValueError("six modulators required")
        for key, value in member["baseline_modulators"].items():
            _unit(value, key)
        if member["ring"] == 1 and member["courier_for"] != founders[member["slot"] - 1]:
            raise ValueError("invalid courier binding")
        if member["founder"] and member["stewards_ring"] != founders.index(member["id"]) + 1:
            raise ValueError("invalid founder responsibility")
    return data


def catalog() -> dict:
    return deepcopy(_catalog())


def _text(value, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("invalid text field")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("control character in text")
    return value


def validate_proposal(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {
            "proposal_id", "goal", "classification", "signals", "ring_evidence", "founder_votes", "source_kind"}:
        raise ValueError("invalid proposal fields")
    proposal_id = value.get("proposal_id")
    if not isinstance(proposal_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", proposal_id):
        raise ValueError("invalid proposal ID")
    goal = _text(value.get("goal"), 2000)
    classification = value.get("classification", "public")
    if classification not in ("public", "restricted", "sealed"):
        raise ValueError("invalid classification")
    source = value.get("source_kind", "user_claims")
    if source not in ("user_claims", "synthetic_fixture"):
        raise ValueError("invalid source kind")
    signals = value.get("signals", {})
    if not isinstance(signals, dict) or set(signals) - set(SIGNALS):
        raise ValueError("invalid signal fields")
    signals = {name: _unit(signals.get(name, default), name) for name, default in SIGNALS.items()}
    evidence = value.get("ring_evidence", {})
    if not isinstance(evidence, dict) or set(evidence) - set("12345678"):
        raise ValueError("invalid evidence ring")
    for refs in evidence.values():
        if not isinstance(refs, list) or len(refs) > 8:
            raise ValueError("at most eight references per ring")
        for ref in refs:
            _text(ref, 128)
        if len(set(refs)) != len(refs):
            raise ValueError("duplicate or invalid evidence reference")
    ballots = value.get("founder_votes")
    if ballots is not None:
        if not isinstance(ballots, dict) or set(ballots) != {str(i) for i in _catalog()["founder_ids"]}:
            raise ValueError("all eight founder votes required")
        if any(not isinstance(v, str) or v not in VOTES for v in ballots.values()):
            raise ValueError("invalid founder vote")
    return {"proposal_id": proposal_id, "goal": goal, "classification": classification,
            "signals": signals, "ring_evidence": {str(i): sorted(evidence.get(str(i), [])) for i in range(1, 9)},
            "founder_votes": deepcopy(ballots), "source_kind": source}


def _opinion(member: dict, signals: dict, modulation: bool) -> dict:
    q, u, r, n, reward, threat, social = (signals[k] for k in SIGNALS)
    targets = {"dopamine": clamp(.5 + (reward - u) / 2),
               "noradrenaline": clamp((threat + u) / 2),
               "acetylcholine": clamp(.5 + q / 2 - u / 4),
               "serotonin": clamp(.6 + social / 4 - threat / 3),
               "gaba": clamp(.45 + r / 3 + threat / 4),
               "glutamate": clamp(.3 + n / 3 + reward / 4)}
    modulators = {name: clamp(.75 * member["baseline_modulators"][name] + .25 * targets[name])
                  if modulation else .5 for name in NAMES}
    policy = neurochemical_policy(dopamine=modulators["dopamine"],
                                  noradrenaline=modulators["noradrenaline"],
                                  acetylcholine=modulators["acetylcholine"], inhibition=modulators["gaba"])
    affect = {"curiosity": clamp(modulators["dopamine"] * modulators["glutamate"]),
              "concern": clamp((modulators["noradrenaline"] + threat + r) / 3),
              "calm": clamp((modulators["serotonin"] + modulators["gaba"]) / 2),
              "social_openness": clamp((modulators["serotonin"] + social) / 2)}
    adjustment = (.12 * (affect["curiosity"] - .25) + .08 * (policy["attention"] - .4375)
                  - .12 * (affect["concern"] - .25)) if modulation else 0.0
    score = clamp(.62*q + .18*reward + .12*n - .35*r - .20*u - .15*threat + .08*social
                  - .1*member["traits"]["risk_aversion"]*r + adjustment)
    return {"member_id": member["id"], "ring": member["ring"], "score": score,
            "vote": "endorse" if score >= .6 else "oppose" if score <= .35 else "defer",
            "modulators": modulators, "affect": affect, "policy_mode": policy["mode"]}


def deliberate(proposal: dict, *, modulation: bool = True) -> dict:
    if type(modulation) is not bool:
        raise ValueError("modulation must be boolean")
    proposal = validate_proposal(proposal)
    model = _catalog()
    by_id = {m["id"]: m for m in model["members"]}
    trace = []

    def record(kind, data):
        event = {"index": len(trace), "kind": kind, "data": data,
                 "previous_hash": trace[-1]["event_hash"] if trace else "0" * 64}
        trace.append({**event, "event_hash": digest(event)})

    record("proposal_received", {"proposal_sha256": digest(proposal), "catalog_sha256": digest(model)})
    opinions = [_opinion(m, proposal["signals"], modulation) for m in model["members"]]
    for opinion in opinions:
        record("member_opinion", opinion)
    reports = []
    for ring in model["rings"][:8]:
        refs = proposal["ring_evidence"][str(ring["id"])]
        courier = model["rings"][0]["member_ids"][ring["id"] - 1]
        report = {"ring": ring["id"], "steward_id": ring["steward_id"], "courier_id": courier,
                  "evidence_refs": refs, "evidence_authenticated": False,
                  "votes": dict(Counter(o["vote"] for o in opinions if o["ring"] == ring["id"]))}
        report["support_ratio"] = (report["votes"].get("endorse", 0) + .5*report["votes"].get("defer", 0))/8
        report["route"] = [{"layer": "limbo", "member_id": courier},
                           {"layer": "specialist_ring", "ring": ring["id"]},
                           {"layer": "founder", "member_id": ring["steward_id"]},
                           {"layer": "founder_council", "ring": 9}]
        reports.append(report)
        record("ring_report", report)
    founders = []
    for number in model["founder_ids"]:
        computed = next(o for o in opinions if o["member_id"] == number)
        member = by_id[number]
        support = reports[member["stewards_ring"] - 1]["support_ratio"]
        synthesis_score = clamp(.65*computed["score"] + .35*support)
        computed_vote = "endorse" if synthesis_score >= .6 else "oppose" if synthesis_score <= .35 else "defer"
        ballot = {"member_id": number, "stewards_ring": member["stewards_ring"],
                  "vote": proposal["founder_votes"][str(number)] if proposal["founder_votes"] else computed_vote,
                  "vote_source": "explicit_input" if proposal["founder_votes"] else "simulated",
                  "report_ring": member["stewards_ring"], "ring_support_ratio": support,
                  "synthesis_score": synthesis_score}
        founders.append(ballot)
        record("founder_ballot", ballot)
    missing = [r["ring"] for r in reports if not r["evidence_refs"]]
    final = ("insufficient_evidence" if missing else "contested" if any(f["vote"] == "oppose" for f in founders)
             else "pending" if any(f["vote"] == "defer" for f in founders) else "endorsed_for_review")
    decision = {"status": final, "missing_evidence_rings": missing,
                "rule": "eight_founders_unanimous; missing_references_block",
                "last_word": "founder_council_within_simulation", "goal": proposal["goal"],
                "evidence_authenticated": False, **AUTHORITY}
    record("founder_synthesis", decision)
    workspace = CognitionCore(workspace_capacity=8, memory_capacity=8)
    workspace.state.self_model["goal"] = proposal["goal"]
    for report in reports:
        workspace.step(report["support_ratio"])
    return {"schema_version": 1, "kind": "klone-council72-round", "catalog_sha256": digest(model),
            "proposal": proposal, "modulation": modulation, "opinions": opinions,
            "ring_reports": reports, "founder_ballots": founders, "decision": decision,
            "functional_metrics": {"reference_coverage": (8 - len(missing))/8,
                                   "founder_endorsements": sum(f["vote"] == "endorse" for f in founders),
                                   "advisory_dissent": sum(o["vote"] == "oppose" for o in opinions if o["ring"] < 9)},
            "trace": trace, "trace_sha256": trace[-1]["event_hash"],
            "functional_workspace": workspace.snapshot(), "functional_probe_digest": workspace.trace_digest(),
            "external_information_scope": "caller_supplied_claims_via_limbo_model", **AUTHORITY}


def replay_matches(report: dict) -> bool:
    try:
        return report == deliberate(report["proposal"], modulation=report["modulation"])
    except (ValueError, KeyError, TypeError, RecursionError):
        return False


def experiment(proposal: dict) -> dict:
    modulated, baseline = deliberate(proposal), deliberate(proposal, modulation=False)
    return {"schema_version": 1, "kind": "klone-council72-experiment",
            "modulated": modulated, "baseline": baseline,
            "comparison": {"changed_opinions": sum(a["vote"] != b["vote"] for a,b in
                                                    zip(modulated["opinions"], baseline["opinions"])),
                           "mean_score_delta": round(sum(a["score"]-b["score"] for a,b in
                                                         zip(modulated["opinions"], baseline["opinions"]))/72, 6)},
            "replay_matches": replay_matches(modulated) and replay_matches(baseline), **AUTHORITY}


def draft_dispatch(report: dict, *, king_id: int, courier_id: int, channel: str, message: str) -> dict:
    if not replay_matches(report):
        raise ValueError("decision report does not replay")
    model = _catalog()
    if type(king_id) is not int or king_id not in model["founder_ids"]:
        raise ValueError("only a founder can issue a draft")
    courier = model["rings"][0]["member_ids"][model["founder_ids"].index(king_id)]
    if type(courier_id) is not int or courier_id != courier:
        raise ValueError("courier does not belong to the issuing founder")
    if report["decision"]["status"] != "endorsed_for_review":
        raise PermissionError("founder synthesis is not endorsed")
    if report["proposal"]["classification"] != "public":
        raise PermissionError("non-public material cannot enter the draft outbox")
    if channel not in ("forum", "social", "documentation", "research"):
        raise ValueError("unknown channel category")
    return {"schema_version": 1, "kind": "klone-council72-draft", "king_id": king_id,
            "courier_id": courier, "channel_category": channel,
            "message": _text(message, 2000), "disclosure": "KLONE · tekoälyneuvoston tarkistamaton luonnos",
            "decision_trace_sha256": report["trace_sha256"], "status": "draft_only",
            "destination": None, "account": None, "owner_review_required": True,
            "issuer_authenticated": False, "message_origin": "caller_supplied",
            "authority_scope": "simulation_only", "delivery_enabled": False, **AUTHORITY}


def demo_proposal() -> dict:
    return {"proposal_id": "synthetic-council72", "source_kind": "synthetic_fixture",
            "goal": "Synteettinen koe: yhdistä kahdeksan ringin havainnot toiminnallisen itsemallin tutkimussuunnitelmaksi.",
            "classification": "public", "signals": {"evidence_quality": .95, "uncertainty": .08,
            "risk": .05, "novelty": .6, "reward": .8, "threat": .04, "social_feedback": .4},
            "ring_evidence": {str(i): [f"synthetic:ring:{i}"] for i in range(1, 9)}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--input", type=Path)
    group.add_argument("--catalog", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home()/"klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        result = catalog() if args.catalog else experiment(demo_proposal() if args.demo else
                                                         json_object(read_bounded(args.input, 65536)))
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
