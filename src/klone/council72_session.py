"""Replayable Council 72 research sessions, source claims and unsent outbox.

No network, database, authenticated identity or execution capability. Persistence
is an explicitly selected new JSON export; prior exports are never rewritten.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import re

from .council72 import AUTHORITY, SIGNALS, VOTES, _text, _replay_equal, catalog, experiment
from .cognition_experiment_lab import _unit
from .cognition_neurocortex import NAMES, clamp, digest
from .evidence_io import json_object, read_bounded, write_new_report
from .hypervisor_runtime import HypervisorRuntime

MAX_ROUNDS = 8
MAX_BYTES = 2 * 1024 * 1024
CLASSES = ("public", "restricted", "sealed")


def _object(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError("invalid session fields")


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", value):
        raise ValueError("invalid identifier")
    return value


def _classification(value):
    if not isinstance(value, str) or value not in CLASSES:
        raise ValueError("invalid classification")
    return value


def validate_step(step):
    _object(step, ("observations",), ("founder_votes", "dispatches"))
    if not isinstance(step["observations"], list) or not 1 <= len(step["observations"]) <= 32:
        raise ValueError("one to 32 observations required")
    model = catalog()
    couriers = {m["id"]: model["founder_ids"].index(m["courier_for"]) + 1
                for m in model["members"] if m.get("courier_for")}
    observations = []
    for raw in step["observations"]:
        _object(raw, ("id", "courier_id", "source_ref", "source_group", "claim_key", "stance", "summary"),
                ("classification", "signals", "supersedes", "observed_at"))
        courier = raw["courier_id"]
        if type(courier) is not int or courier not in couriers:
            raise ValueError("observations must enter through a Limbo courier")
        if not isinstance(raw["stance"], str) or raw["stance"] not in ("supports", "contradicts", "unknown"):
            raise ValueError("invalid observation stance")
        signals = raw.get("signals", {})
        if not isinstance(signals, dict) or set(signals) - set(SIGNALS):
            raise ValueError("invalid observation signals")
        signals = {k: _unit(signals.get(k, v), k) for k, v in SIGNALS.items()}
        observations.append({"id": _identifier(raw["id"]), "courier_id": courier,
            "ring": couriers[courier], "source_ref": _text(raw["source_ref"], 256),
            "source_group": _identifier(raw["source_group"]), "claim_key": _identifier(raw["claim_key"]),
            "stance": raw["stance"], "summary": _text(raw["summary"], 512),
            "classification": _classification(raw.get("classification", "public")), "signals": signals,
            "supersedes": _identifier(raw["supersedes"]) if raw.get("supersedes") is not None else None,
            "observed_at": _text(raw["observed_at"], 64) if raw.get("observed_at") is not None else None})
    ballots = step.get("founder_votes")
    if ballots is not None and (not isinstance(ballots, dict) or
            set(ballots) != {str(i) for i in model["founder_ids"]} or
            any(not isinstance(v, str) or v not in VOTES for v in ballots.values())):
        raise ValueError("all eight valid founder votes required")
    dispatches = step.get("dispatches", [])
    if not isinstance(dispatches, list) or len(dispatches) > 8:
        raise ValueError("at most eight dispatches per round")
    normal = []
    for raw in dispatches:
        _object(raw, ("king_id", "courier_id", "channel", "message"))
        king, courier = raw["king_id"], raw["courier_id"]
        if type(king) is not int or king not in model["founder_ids"] or type(courier) is not int or \
                courier not in couriers or model["founder_ids"][couriers[courier] - 1] != king:
            raise ValueError("dispatch must bind a founder to its own Limbo courier")
        if not isinstance(raw["channel"], str) or raw["channel"] not in ("forum", "social", "documentation", "research"):
            raise ValueError("invalid channel category")
        normal.append({**raw, "message": _text(raw["message"], 2000)})
    return {"observations": observations, "founder_votes": deepcopy(ballots), "dispatches": normal}


def validate_request(request):
    _object(request, ("session_id", "goal", "steps"), ("classification", "source_kind"))
    steps = request["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_ROUNDS:
        raise ValueError("one to eight rounds required")
    source = request.get("source_kind", "user_claims")
    if not isinstance(source, str) or source not in ("synthetic_fixture", "user_claims"):
        raise ValueError("invalid source kind")
    # Keep the canonical input in the caller's schema, not the derived ring fields.
    normalized = []
    for step in steps:
        value = validate_step(step)
        value["observations"] = [{k: v for k, v in o.items() if k != "ring"} for o in value["observations"]]
        normalized.append(value)
    result = {"session_id": _identifier(request["session_id"]), "goal": _text(request["goal"], 2000),
              "classification": _classification(request.get("classification", "public")),
              "source_kind": source, "steps": normalized}
    if len(json.dumps(result, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError("session input too large")
    return result


def _assess(active):
    conflicts = []
    for key in sorted({o["claim_key"] for o in active}):
        claims = [o for o in active if o["claim_key"] == key]
        if {"supports", "contradicts"} <= {o["stance"] for o in claims}:
            conflicts.append({"claim_key": key, "observation_ids": sorted(o["id"] for o in claims),
                              "rings": sorted({o["ring"] for o in claims})})
    rings, signals, refs = [], {}, {}
    for ring in range(1, 9):
        claims = [o for o in active if o["ring"] == ring]
        groups = []
        for group in sorted({o["source_group"] for o in claims}):
            rows = [o for o in claims if o["source_group"] == group]
            supports = all(o["stance"] == "supports" for o in rows)
            values = {k: (max if k in ("uncertainty", "risk", "threat") else min)(o["signals"][k] for o in rows)
                      for k in SIGNALS}
            if not supports:
                values["evidence_quality"], values["uncertainty"] = 0., 1.
            groups.append({"group": group, "supports": supports, "signals": values,
                           "reference": sorted(o["id"] for o in rows)[0]})
        eligible = [g for g in groups if g["supports"]]
        refs[str(ring)] = [g["reference"] for g in eligible[:8]]
        signals[str(ring)] = ({k: (max if k in ("uncertainty", "risk", "threat") else min)
                              (g["signals"][k] for g in groups) for k in SIGNALS} if groups else dict(SIGNALS))
        rings.append({"ring": ring, "active_observations": len(claims),
                      "claimed_source_groups": len(groups), "supporting_source_groups": len(eligible),
                      "quorum_met": len(eligible) >= 2, "authenticated_sources": 0,
                      "unknown_observation_ids": sorted(o["id"] for o in claims if o["stance"] == "unknown"),
                      "references_truncated": len(eligible) > 8})
    return rings, signals, refs, conflicts


def run_session(request: dict) -> dict:
    request = validate_request(request)
    model = catalog()
    original = {str(m["id"]): dict(m["baseline_modulators"]) for m in model["members"]}
    state = deepcopy(original)
    all_observations, replaced, events, outbox = {}, set(), [], []
    classification = request["classification"]
    latest = None
    for index, raw in enumerate(request["steps"], 1):
        step = validate_step(raw)
        for observation in step["observations"]:
            number, old_id = observation["id"], observation["supersedes"]
            if number in all_observations:
                raise ValueError("observation IDs are append-only and unique")
            if old_id is not None:
                old = all_observations.get(old_id)
                if old is None or old_id in replaced or any(old[k] != observation[k]
                        for k in ("courier_id", "source_group", "claim_key")):
                    raise ValueError("correction must reference one active claim from the same courier and source")
                if CLASSES.index(observation["classification"]) < CLASSES.index(old["classification"]):
                    raise ValueError("correction cannot lower classification")
                replaced.add(old_id)
            all_observations[number] = observation
            classification = CLASSES[max(CLASSES.index(classification), CLASSES.index(observation["classification"]))]
        active = [v for k, v in all_observations.items() if k not in replaced]
        rings, signals, refs, conflicts = _assess(active)
        context = {"member_modulators": state, "ring_signals": signals}
        proposal = {"proposal_id": request["session_id"] + ":" + str(index), "goal": request["goal"],
                    "source_kind": request["source_kind"], "classification": classification,
                    "ring_evidence": refs, "founder_votes": step["founder_votes"]}
        # proposal IDs remain bounded even for a 64-character session identifier.
        proposal["proposal_id"] = "session-" + digest([request["session_id"], index])[:48]
        latest = experiment(proposal, context=context)
        round_report = latest["modulated"]
        missing = [r["ring"] for r in rings if not r["quorum_met"]]
        review = ("contradictory_evidence" if conflicts else "insufficient_sources" if missing
                  else round_report["decision"]["status"])
        plane = asdict(HypervisorRuntime().plan(room_id="public-room", actor_role="evaluator",
            permission="propose", trace_id="council-" + digest([request["session_id"], index])[:32],
            classification_level={"public": "public", "restricted": "personal", "sealed": "intimate"}[classification]))
        # A preview neither authenticates the caller nor authorizes dispatch.
        plane.update({"preview_only": True, "caller_authenticated": False})
        old_state = state
        state = {str(o["member_id"]): {k: clamp(.9 * o["modulators"][k] + .1 * original[str(o["member_id"])][k])
                                      for k in NAMES} for o in round_report["opinions"]}
        event = {"index": index, "input_sha256": digest(raw), "classification": classification,
                 "active_observation_count": len(active), "corrected_observation_ids": sorted(replaced),
                 "rings": rings, "conflicts": conflicts, "missing_quorum_rings": missing,
                 "review_status": review, "founder_ballots": round_report["founder_ballots"],
                 "decision_trace_sha256": round_report["trace_sha256"],
                 "previous_state_sha256": digest(old_state), "state_sha256": digest(state),
                 "mean_state_delta": round(sum(abs(state[m][k] - old_state[m][k])
                                               for m in state for k in NAMES) / 432, 6),
                 "permission_preview": plane,
                 "previous_hash": events[-1]["event_hash"] if events else "0" * 64}
        event["event_hash"] = digest(event)
        events.append(event)
        for number, dispatch in enumerate(step["dispatches"], 1):
            status = ("blocked_private" if classification != "public" else
                      "blocked_policy" if plane["decision"] != "allowed" else
                      "pending_owner_review" if review == "endorsed_for_review" else "blocked_" + review)
            outbox.append({"id": f"{index}:{number}", "round": index, **dispatch,
                           "origin_event_hash": event["event_hash"], "status": status,
                           "disclosure": "KLONE · tekoälyneuvoston tarkistamaton luonnos",
                           "owner_review_required": True, "issuer_authenticated": False,
                           "destination": None, "account": None, "delivery_enabled": False, **AUTHORITY})
    for item in outbox:
        if item["round"] != len(events):
            item["status"] = "stale_requires_review"
    report = {"schema_version": 1, "kind": "klone-council72-session", "request": request,
              "catalog_sha256": digest(model), "rounds": events, "member_state": state,
              "latest_experiment": latest, "outbox": outbox, "classification": classification,
              "observation_count": len(all_observations), "active_observation_count": len(active),
              "trace_sha256": events[-1]["event_hash"], "provenance_authenticated": False,
              "source_independence": "caller_declared_groups_only", "persistence": "explicit_new_json_export",
              "memory_scope": "isolated_research_session", "audit_scope": "replayable_session_chain_only",
              "replay_validation": "recompute_request_with_same_code_and_catalog", **AUTHORITY}
    if len(json.dumps(report, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError("session report too large")
    return report


def session_replays(report):
    try:
        return _replay_equal(report, run_session(report["request"]))
    except (KeyError, ValueError, TypeError, RecursionError, OverflowError):
        return False


def continue_session(report, step):
    if not session_replays(report):
        raise ValueError("previous session does not replay")
    request = deepcopy(report["request"])
    request["steps"].append(deepcopy(step))
    return run_session(request)


def demo_session():
    model = catalog()
    observations = []
    for ring in range(1, 9):
        courier = model["rings"][0]["member_ids"][ring - 1]
        for source in (1, 2):
            observations.append({"id": f"r{ring}-s{source}", "courier_id": courier,
                "source_ref": f"synthetic:ring:{ring}:source:{source}", "source_group": f"fixture-{source}",
                "claim_key": f"ring-{ring}-ready", "stance": "supports", "summary": "Synteettinen lähtöhavainto.",
                "signals": {"evidence_quality": .95, "uncertainty": .08, "risk": .05, "novelty": .6,
                            "reward": .8, "threat": .04, "social_feedback": .4}})
    draft = {"king_id": 9, "courier_id": 27, "channel": "research", "message": "Synteettinen tutkimusluonnos tarkistukseen."}
    changed = {**observations[3], "id": "new-threat", "claim_key": "ring-2-ready", "stance": "contradicts",
               "source_group": "fixture-3", "summary": "Synteettinen ristiriita ja kohonnut uhka.",
               "signals": {**observations[3]["signals"], "risk": .8, "threat": .9, "uncertainty": .8}}
    correction = {**changed, "id": "corrected-threat", "supersedes": "new-threat", "stance": "supports",
                  "summary": "Uusi synteettinen havainto korjaa aiemman väitteen; vanha jää lokiin.",
                  "signals": dict(observations[3]["signals"])}
    return {"session_id": "synthetic-session72", "goal": "Tutki rinkien tiedonkulkua, ristiriitaa ja simuloidun tunnetilan palautumista.",
            "source_kind": "synthetic_fixture", "steps": [{"observations": observations, "dispatches": [draft]},
                {"observations": [changed], "dispatches": [draft]},
                {"observations": [correction], "dispatches": [draft]}]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--demo", action="store_true")
    choice.add_argument("--input", type=Path)
    choice.add_argument("--verify", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home()/"klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if args.previous or args.output:
                raise ValueError("--verify reads one report and prints a check summary")
            report = json_object(read_bounded(args.verify, MAX_BYTES))
            if not session_replays(report):
                raise ValueError("session does not replay with this code and catalog")
            print(json.dumps({"kind": "klone-council72-session-check", "replay_matches": True,
                              "rounds": len(report["rounds"]), "provenance_authenticated": False, **AUTHORITY}))
            return 0
        if args.previous:
            if args.demo:
                raise ValueError("continuation requires --input with one new step")
            report = continue_session(json_object(read_bounded(args.previous, MAX_BYTES)),
                                      json_object(read_bounded(args.input, 65536)))
        else:
            report = run_session(demo_session() if args.demo else json_object(read_bounded(args.input, MAX_BYTES)))
        rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(rendered.encode()) > MAX_BYTES:
            raise ValueError("rendered session report too large")
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
