"""Lossless claim consolidation, eight founder briefings and manual work packets.

Pure derivation from a replayable review. Original observations remain claims;
consolidation does not write Memory Core, authenticate sources or run commands.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from .acceptance_matrix import DOMAINS
from .cognition_neurocortex import NAMES, digest
from .council72 import AUTHORITY, _replay_equal, catalog
from .council72_review import DOMAIN_CHECKS, DOMAIN_RING, review_replays, review_session
from .council72_session import MAX_BYTES, demo_session, run_session, validate_step
from .evidence_io import json_object, read_bounded, write_new_report

# Trusted repository paths, never taken from observation text or imported tasks.
DOMAIN_FILES = {
    "hypervisor": ["src/klone/hypervisor_runtime.py", "src/klone/hypervisor_dispatch.py"],
    "permissions": ["src/klone/hypervisor_safe_pipeline.py"],
    "audit": ["src/klone/council72_memory.py", "src/klone/hypervisor_audit_adapter.py"],
    "memory": ["src/klone/memory.py", "src/klone/repository.py"],
    "cognition": ["src/klone/council72.py", "src/klone/council72_session.py"],
    "research": ["src/klone/research_workflow.py"],
    "genomics": ["src/klone/genomics_preflight.py"],
    "media": ["src/klone/art.py"],
    "simulation": ["src/klone/simulation.py"],
    "android": ["tools/local_deploy.py", "src/klone/evidence_io.py"],
    "ci": [".github/workflows/klone-regression.yml"],
    "deployment": ["tools/local_deploy.py"],
}


def _checks(domain):
    if domain == "media":
        return ["tests/test_phase_v1_1.py", "tests/test_phase_v1_2.py"]
    target = DOMAIN_CHECKS[domain]
    return [target] if target and target.startswith("tests/") else []


def _commands(tests):
    if not tests:
        return None
    # Only constant catalog paths reach the shell text. Caller text stays data.
    return '\n'.join([
        '(', 'set -eu',
        'KLONE_ROOT="${KLONE_ROOT:-$HOME/klone-next}"',
        'KLONE_PY="${KLONE_PY:-$HOME/klone-next/.venv/bin/python}"',
        '[ -d "$KLONE_ROOT/src/klone" ] || { echo "Tarkista KLONE_ROOT"; exit 1; }',
        '[ -x "$KLONE_PY" ] || { echo "Tarkista KLONE_PY"; exit 1; }',
        'cd "$KLONE_ROOT" || exit 1',
        'git status --short', 'git branch --show-current', 'git rev-parse HEAD',
        'PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 "$KLONE_PY" -m pytest -p no:cacheprovider -q '
        + ' '.join(tests),
        'git diff --check', 'git diff --stat', ')',
    ])


def _work_packet(domain, state, route):
    tests = _checks(domain)
    return {"domain": domain, "caller_declared_state": state, "route": route,
        "related_files": DOMAIN_FILES[domain] + tests,
        "test_targets": tests, "commands_text": _commands(tests),
        "coverage": "art_image_subset_only" if domain == "media" else
                    "workflow_review_only" if domain == "ci" else "mapped_regression_subset",
        "test_execution_status": "not_run_by_briefing", "expected_commit": None,
        "verification": "Kirjaa kohdistuksen tulos uutena testiajona samalla commitilla. "
                        "Mahdollisen korjauksen jälkeen aja kohdistus ja koko pytest-sarja.",
        "execution_enabled": False}


def work_check_catalog():
    """Packaged viewer allowlist, excluding caller states and per-session routes."""
    fields = ("domain", "related_files", "test_targets", "commands_text", "coverage")
    return {"schema_version": 1, "kind": "klone-council72-work-checks",
            "domains": [{k: v for k, v in _work_packet(d, "unverified", None).items() if k in fields}
                        for d in sorted(DOMAINS)]}


def _build(review):
    session = review["session"]
    model = catalog()
    by_id = {m["id"]: m for m in model["members"]}
    history = []
    for index, step in enumerate(session["request"]["steps"], 1):
        history.extend({**o, "round": index} for o in validate_step(step)["observations"])
    replaced = {o["supersedes"]: o["id"] for o in history if o["supersedes"] is not None}
    active = [o for o in history if o["id"] not in replaced]
    latest = session["rounds"][-1]
    conflicting = {c["claim_key"] for c in latest["conflicts"]}
    claims = []
    for ring, key in sorted({(o["ring"], o["claim_key"]) for o in history}):
        rows = [o for o in active if o["ring"] == ring and o["claim_key"] == key]
        stances = {o["stance"] for o in rows}
        status = ("contested" if key in conflicting else "unexamined" if stances == {"unknown"}
                  else "reported_support" if stances == {"supports"}
                  else "reported_opposition" if stances == {"contradicts"} else "mixed_unknown")
        claims.append({"ring": ring, "claim_key": key, "epistemic_status": status,
            "classification": session["classification"],
            "history_observation_ids": sorted(o["id"] for o in history
                if o["ring"] == ring and o["claim_key"] == key),
            "active_observation_ids": sorted(o["id"] for o in rows),
            "supports": sorted(o["id"] for o in rows if o["stance"] == "supports"),
            "contradicts": sorted(o["id"] for o in rows if o["stance"] == "contradicts"),
            "unknown": sorted(o["id"] for o in rows if o["stance"] == "unknown"),
            "caller_declared_source_groups": sorted({o["source_group"] for o in rows}),
            "truth_verified": False})
    opinions = {o["member_id"]: o for o in session["latest_experiment"]["modulated"]["opinions"]}
    cases = review["source_analysis"]["cases"]
    founders, packets = [], []
    for ring in model["rings"][:8]:
        number = ring["id"]
        king = by_id[ring["steward_id"]]
        courier = next(m for m in model["members"] if m.get("courier_for") == king["id"])
        route = {"ring": number, "founder_id": king["id"], "founder_name": king["name"],
                 "courier_id": courier["id"], "courier_name": courier["name"]}
        tasks = [t for t in review["plan"]["tasks"] if t["route"]["ring"] == number]
        domain_packets = [_work_packet(d, review["options"]["domain_states"][d], route)
                          for d in DOMAINS if DOMAIN_RING[d] == number]
        packets.extend(domain_packets)
        vote_history = []
        for event in session["rounds"]:
            ballot = next(b for b in event["founder_ballots"] if b["member_id"] == king["id"])
            vote_history.append({"round": event["index"], "vote": ballot["vote"],
                "origin": ballot["vote_source"], "review_status": event["review_status"],
                "event_hash": event["event_hash"]})
        founders.append({**route, "ring_name": ring["dante_label"], "responsibility": ring["domain"],
            "founder_task": king["task"], "founder_vote": vote_history[-1]["vote"],
            "vote_history": vote_history,
            "members": [{"id": mid, "name": by_id[mid]["name"], "task": by_id[mid]["task"],
                "vote": opinions[mid]["vote"], "score": opinions[mid]["score"],
                "signal_ring": (by_id[mid].get("stewards_ring") or
                    (by_id[by_id[mid]["courier_for"]]["stewards_ring"]
                     if by_id[mid].get("courier_for") else by_id[mid]["ring"]))}
                for mid in ring["member_ids"]],
            "affect": {"scope": "retained_state_from_profile_baseline",
                "baseline": deepcopy(king["baseline_modulators"]),
                "current": deepcopy(session["member_state"][str(king["id"])]),
                "delta": {k: round(session["member_state"][str(king["id"])][k]
                                    - king["baseline_modulators"][k], 6) for k in NAMES}},
            "claims": [c for c in claims if c["ring"] == number],
            "conflict_claim_keys": sorted(c["claim_key"] for c in latest["conflicts"] if number in c["rings"]),
            "unknown_observation_ids": sorted(o["id"] for o in active if o["ring"] == number and o["stance"] == "unknown"),
            "quorum": deepcopy(latest["rings"][number - 1]),
            "source_withdrawal_cases": [c["removed_source_group"] for c in cases
                if number in c["affected_rings"] and c["review_status_changed"]],
            "source_withdrawal_coverage_complete": review["source_analysis"]["coverage_complete"],
            "task_ids": [t["id"] for t in tasks],
            "allocated_minutes": sum(t["estimated_minutes"] for t in tasks if t["allocation"] == "selected"),
            "domain_work_packets": domain_packets})
    selected = [t for t in review["plan"]["tasks"] if t["allocation"] == "selected"]
    # Stay at the highest selected priority, then take the shortest whole task.
    next_task = min(selected, key=lambda t: (-t["priority_score"], t["estimated_minutes"], t["id"])) if selected else None
    next_step = None
    if next_task:
        packet = next((p for p in packets if p["domain"] == next_task.get("domain")), None)
        next_step = {"task": deepcopy(next_task), "work_packet": packet,
            "selection_policy": "highest_selected_priority_then_shortest_then_id",
            "change_proposal": None,
            "open_questions": ["Mikä commit ja testiympäristö tutkitaan?",
                               "Mitä alkuperäinen traceback tai lähdeaineisto osoittaa?"],
            "checklist": ["Varmista hakemisto, virtuaaliympäristö ja commit.",
                "Tarkista alkuperäiset havainnot ja säilytä eriävät kannat.",
                "Kirjaa tarkistuksen tulos uutena evidenssinä.",
                "Ehdota yhtä rajattua korjausta vasta toistetun virheen perusteella.",
                "Sulje regressio vasta testikohtaisen varmistuksen jälkeen."],
            "execution_enabled": False}
    report = {"schema_version": 1, "kind": "klone-council72-briefing", "review": deepcopy(review),
        "review_sha256": review["review_sha256"], "session_trace_sha256": session["trace_sha256"],
        "classification": session["classification"], "goal": session["request"]["goal"],
        "founders": founders,
        "collective": {"review_status": latest["review_status"],
            "founder_ballots": deepcopy(latest["founder_ballots"]),
            "minority_founder_ids": [b["member_id"] for b in latest["founder_ballots"] if b["vote"] != "endorse"],
            "conflict_claim_keys": sorted(conflicting),
            "missing_quorum_rings": list(latest["missing_quorum_rings"]),
            "allocated_minutes": review["plan"]["allocated_minutes"],
            "budget_minutes": review["options"]["budget_minutes"],
            "common_goal_achieved": None},
        "consolidation": {"kind": "referenced_claim_index_only", "claims": claims,
            "corrections": [{"superseded_id": old, "replacement_id": new}
                            for old, new in sorted(replaced.items())],
            "history_observation_count": len(history), "active_observation_count": len(active),
            "originals_preserved_in_review": True, "memory_write_enabled": False},
        "next_step": next_step, "domain_work_packets": sorted(packets, key=lambda p: p["domain"]),
        "provenance_authenticated": False, "manual_review_required": True,
        "source_independence": "caller_declared_groups_only", "execution_enabled": False, **AUTHORITY}
    report["briefing_sha256"] = digest(report)
    if len((json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode("utf-8")) > MAX_BYTES:
        raise ValueError("briefing report too large")
    return report


def build_briefing(review):
    if not review_replays(review):
        raise ValueError("review must replay before briefing")
    # Nested source reports must use their canonical numeric representation.
    return _build(review_session(review["session"], **review["options"]))


def briefing_replays(report):
    try:
        return _replay_equal(report, build_briefing(report["review"]))
    except (KeyError, ValueError, TypeError, RecursionError, OverflowError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--input", type=Path, help="replayable review JSON")
    choice.add_argument("--demo", action="store_true")
    choice.add_argument("--verify", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home()/"klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if args.output:
                raise ValueError("--verify cannot write an output")
            if not briefing_replays(json_object(read_bounded(args.verify, MAX_BYTES))):
                raise ValueError("briefing does not replay")
            print(json.dumps({"kind": "klone-council72-briefing-check", "replay_matches": True,
                              "provenance_authenticated": False, **AUTHORITY}))
            return 0
        review = (review_session(run_session(demo_session())) if args.demo else
                  json_object(read_bounded(args.input, MAX_BYTES)))
        rendered = json.dumps(build_briefing(review), ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
