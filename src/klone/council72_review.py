"""Bounded evidence-withdrawal experiments and explainable development queues.

Source withdrawal changes only the final round's active evidence, using that
round's original incoming state and ballots. It never rewrites session history.
Time allocations are planning estimates; this module executes no tasks.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from .acceptance_matrix import DOMAINS
from .cognition_neurocortex import digest
from .council72 import AUTHORITY, _replay_equal, catalog, experiment
from .council72_session import (
    MAX_BYTES, _assess, demo_session, run_session, session_replays, validate_step,
)
from .development_priorities import prioritize_quality_work
from .evidence_io import json_object, read_bounded, write_new_report

# Existing catalog responsibilities: routing, goals, memory, resources, recovery,
# competing explanations, bounded execution and evidence integrity.
DOMAIN_RING = {
    "hypervisor": 7, "permissions": 7, "audit": 8, "memory": 3,
    "cognition": 2, "research": 6, "genomics": 8, "media": 1,
    "simulation": 6, "android": 4, "ci": 8, "deployment": 7,
}
DOMAIN_CHECKS = {
    "hypervisor": "tests/test_hypervisor_runtime_contract.py",
    "permissions": "tests/test_hypervisor_safe_pipeline.py",
    "audit": "tests/test_council72_memory.py",
    "memory": "tests/test_memory_phase_2b3.py",
    "cognition": "tests/test_council72_session.py",
    "research": "tests/test_research_workflow.py",
    "genomics": "tests/test_genomics_preflight.py",
    "media": None,  # No dedicated media regression is mapped yet.
    "simulation": "tests/test_phase_s1_1.py",
    "android": "tests/test_local_deploy.py",
    "ci": ".github/workflows/klone-regression.yml",
    "deployment": "tests/test_local_deploy.py",
}


def _options(domain_states, budget_minutes, max_tasks, max_source_groups):
    for name, value, upper in (("budget_minutes", budget_minutes, 480),
                               ("max_tasks", max_tasks, 32),
                               ("max_source_groups", max_source_groups, 32)):
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError(f"{name} must be an integer between one and {upper}")
    states = dict.fromkeys(DOMAINS, "unverified") if domain_states is None else domain_states
    prioritize_quality_work(states)  # Reuse the existing complete-domain contract.
    return {"domain_states": dict(states), "budget_minutes": budget_minutes,
            "max_tasks": max_tasks, "max_source_groups": max_source_groups}


def _review_status(rings, conflicts, decision):
    return ("contradictory_evidence" if conflicts else
            "insufficient_sources" if any(not r["quorum_met"] for r in rings) else decision)


def _active_observations(session):
    observations, replaced = {}, set()
    for raw in session["request"]["steps"]:
        for row in validate_step(raw)["observations"]:
            observations[row["id"]] = row
            if row["supersedes"] is not None:
                replaced.add(row["supersedes"])
    return [row for key, row in observations.items() if key not in replaced]


def _route(model, ring):
    king = model["rings"][ring - 1]["steward_id"]
    courier = next(m for m in model["members"] if m.get("courier_for") == king)
    founder = next(m for m in model["members"] if m["id"] == king)
    return {"ring": ring, "founder_id": king, "founder_name": founder["name"],
            "courier_id": courier["id"], "courier_name": courier["name"]}


def _build(session, options):
    model = catalog()
    active = _active_observations(session)
    groups = sorted({row["source_group"] for row in active})
    tested = groups[:options["max_source_groups"]]
    baseline = session["latest_experiment"]["modulated"]
    latest = session["rounds"][-1]
    cases = []
    for group in tested:
        kept = [o for o in active if o["source_group"] != group]
        rings, signals, refs, conflicts = _assess(kept)
        proposal = {**baseline["proposal"], "ring_evidence": refs}
        context = {**baseline["context"], "ring_signals": signals}
        changed = experiment(proposal, context=context)["modulated"]
        status = _review_status(rings, conflicts, changed["decision"]["status"])
        old_votes = {o["member_id"]: o["vote"] for o in baseline["opinions"]}
        old_scores = {o["member_id"]: o["score"] for o in baseline["opinions"]}
        old_founders = {o["member_id"]: o["vote"] for o in baseline["founder_ballots"]}
        cases.append({"removed_source_group": group,
            "removed_observation_ids": sorted(o["id"] for o in active if o["source_group"] == group),
            "affected_rings": sorted({o["ring"] for o in active if o["source_group"] == group}),
            "review_status": status, "review_status_changed": status != latest["review_status"],
            "missing_quorum_rings": [r["ring"] for r in rings if not r["quorum_met"]],
            "conflict_claim_keys": [c["claim_key"] for c in conflicts],
            "changed_member_votes": sum(o["vote"] != old_votes[o["member_id"]] for o in changed["opinions"]),
            "mean_absolute_score_delta": round(sum(abs(o["score"] - old_scores[o["member_id"]])
                                                   for o in changed["opinions"]) / 72, 6),
            "changed_founder_ids": [f["member_id"] for f in changed["founder_ballots"]
                                    if f["vote"] != old_founders[f["member_id"]]],
            "founder_vote_policy": "explicit_input_preserved_simulated_votes_recomputed",
            **AUTHORITY})

    tasks = []

    def add(number, kind, ring, title, priority, minutes, refs, done_check, **details):
        tasks.append({"id": number, "kind": kind, "title": title, "priority_score": priority,
                      "estimated_minutes": minutes, "evidence_observation_ids": sorted(set(refs)),
                      "done_check": done_check, "route": _route(model, ring),
                      "execution_enabled": False, **details})

    for c in latest["conflicts"]:
        for ring in c["rings"]:
            add(f"conflict:{c['claim_key']}:{ring}", "resolve_conflict", ring,
                f"Selvitä ristiriita: {c['claim_key']}", 30, 20, c["observation_ids"],
                "Kirjaa vastakkaisten havaintojen perustelut; korjaa vain uudella supersedes-havainnolla. "
                "Säilytä avoin ristiriita, jos näyttö ei ratkaise sitä.")
    for ring in latest["rings"]:
        number = ring["ring"]
        rows = [o for o in active if o["ring"] == number]
        if not ring["quorum_met"]:
            add(f"sources:{number}", "collect_sources", number,
                f"Täydennä ringin {number} lähdeaineisto", 20, 15, [o["id"] for o in rows],
                "Tarkista vähintään kaksi puoltavaa lähderyhmää ja kirjaa riippumattomuuden rajat; "
                "tuntematon havainto ei muutu puoltavaksi ilman uutta näyttöä.")
        if ring["unknown_observation_ids"]:
            add(f"unknown:{number}", "check_unknown", number,
                f"Tutki ringin {number} avoimet havainnot", 18, 10, ring["unknown_observation_ids"],
                "Liitä mitattava tarkistus jokaiseen avoimeen havaintoon; säilytä unknown, jos tulos puuttuu.")
    for ballot in latest["founder_ballots"]:
        if ballot["vote"] != "endorse":
            ring = ballot["stewards_ring"]
            add(f"dissent:{ballot['member_id']}", "review_dissent", ring,
                f"Käsittele perustajan {ballot['member_id']} eriävä tai odottava kanta", 17, 10,
                [o["id"] for o in active if o["ring"] == ring],
                "Kirjaa vähemmistöperustelu ja uusi arvio uutena kierroksena. Aiempi kanta säilyy.",
                founder_vote=ballot["vote"])
    sensitive_rings = sorted({r for case in cases if case["review_status_changed"] for r in case["affected_rings"]})
    for ring in sensitive_rings:
        add(f"sensitivity:{ring}", "review_sensitivity", ring,
            f"Arvioi ringin {ring} riippuvuus yksittäisestä lähderyhmästä", 16, 10,
            [o["id"] for o in active if o["ring"] == ring],
            "Selitä lähteen poistamisen vaikutus ja säilytä tarvittava pidättyvä kanta. "
            "Lisänäyttöä kerätään tarvittaessa; kokeen tarkoitus ei ole pakottaa hyväksyntää.")

    for quality in prioritize_quality_work(options["domain_states"]):
        domain, state = quality["domain"], quality["state"]
        add("domain:" + domain, "development_check", DOMAIN_RING[domain],
            f"{'Korjaa epäonnistunut tarkistus' if state == 'failed' else 'Varmenna osa-alue'}: {domain}",
            quality["priority_score"], 25 if state == "failed" else 15, [],
            "Tallenna tarkistuksen commit, ympäristö, komento ja alkuperäinen tulos. "
            "Work-, CI- ja Android-tulokset pidetään erillisinä.", domain=domain,
            caller_declared_state=state, recommended_action=quality["recommended_action"],
            check_target=DOMAIN_CHECKS[domain],
            check_target_kind="unmapped" if DOMAIN_CHECKS[domain] is None else
                              "workflow" if domain == "ci" else "test")
    tasks.sort(key=lambda row: (-row["priority_score"], row["id"]))
    remaining, selected = options["budget_minutes"], 0
    for task in tasks:
        if selected >= options["max_tasks"]:
            task["allocation"] = "deferred_task_limit"
        elif task["estimated_minutes"] > remaining:
            task["allocation"] = "deferred_budget"
        else:
            task["allocation"] = "selected"
            remaining -= task["estimated_minutes"]
            selected += 1
    report = {"schema_version": 1, "kind": "klone-council72-review", "session": deepcopy(session),
        "options": deepcopy(options), "classification": session["classification"],
        "session_trace_sha256": session["trace_sha256"], "catalog_sha256": digest(model),
        "source_analysis": {"scope": "final_active_evidence_with_original_incoming_state",
            "history_rewritten": False, "baseline_review_status": latest["review_status"],
            "active_source_groups": len(groups), "tested_source_groups": tested,
            "omitted_source_groups": groups[len(tested):], "coverage_complete": len(tested) == len(groups),
            "status_sensitive_cases": sum(c["review_status_changed"] for c in cases), "cases": cases},
        "plan": {"tasks": tasks, "selected_count": selected, "deferred_count": len(tasks) - selected,
            "allocated_minutes": options["budget_minutes"] - remaining, "remaining_minutes": remaining,
            "allocation_policy": "priority_desc_then_id_first_fit_no_task_splitting",
            "time_estimates_only": True, "domain_state_source": "caller_declared_not_verified",
            "execution_enabled": False}, "provenance_authenticated": False,
        "source_independence": "caller_declared_groups_only", "manual_review_required": True, **AUTHORITY}
    report["review_sha256"] = digest(report)
    if len((json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()) > MAX_BYTES:
        raise ValueError("review report too large")
    return report


def review_session(session, *, domain_states=None, budget_minutes=60, max_tasks=8, max_source_groups=16):
    options = _options(domain_states, budget_minutes, max_tasks, max_source_groups)
    if not session_replays(session):
        raise ValueError("session must replay before review")
    return _build(session, options)


def review_replays(report):
    try:
        return _replay_equal(report, review_session(report["session"], **report["options"]))
    except (KeyError, ValueError, TypeError, RecursionError, OverflowError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--demo", action="store_true")
    choice.add_argument("--input", type=Path, help="replayable session report JSON")
    choice.add_argument("--verify", type=Path)
    parser.add_argument("--states", type=Path, help="all twelve caller-declared domain states")
    parser.add_argument("--budget-minutes", type=int, default=60)
    parser.add_argument("--max-tasks", type=int, default=8)
    parser.add_argument("--max-source-groups", type=int, default=16)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home()/"klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if args.output or args.states:
                raise ValueError("--verify reads one report and prints a check summary")
            report = json_object(read_bounded(args.verify, MAX_BYTES))
            if not review_replays(report):
                raise ValueError("review does not replay")
            print(json.dumps({"kind": "klone-council72-review-check", "replay_matches": True,
                              "provenance_authenticated": False, **AUTHORITY}))
            return 0
        session = run_session(demo_session()) if args.demo else json_object(read_bounded(args.input, MAX_BYTES))
        states = json_object(read_bounded(args.states, 4096)) if args.states else None
        report = review_session(session, domain_states=states, budget_minutes=args.budget_minutes,
                                max_tasks=args.max_tasks, max_source_groups=args.max_source_groups)
        rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
