"""Explicit pre-run acceptance contracts; hashes bind criteria, not chronology."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .acceptance_matrix import DOMAINS
from .council72 import AUTHORITY, _replay_equal, _text
from .council72_session import _identifier, _classification
from .evidence_io import json_object, read_bounded, write_new_report
from .evidence_network import REQUIRED, SHA, canonical

MAX_CONTRACT = 32768


def register_contract(spec):
    if not isinstance(spec, dict) or set(spec) != {
            "contract_id", "goal", "target_commit", "classification", "criteria"}:
        raise ValueError("invalid contract fields")
    commit = spec["target_commit"]
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("exact target commit required")
    if not isinstance(spec["criteria"], list) or not 1 <= len(spec["criteria"]) <= 16:
        raise ValueError("one to sixteen criteria required")
    rows, ids, claims = [], set(), set()
    for c in spec["criteria"]:
        if not isinstance(c, dict) or set(c) != {"id", "claim_key", "domain", "stage", "environment", "min_passed"}:
            raise ValueError("invalid criterion fields")
        ident, claim = _identifier(c["id"]), _identifier(c["claim_key"])
        if ident in ids or claim in claims:
            raise ValueError("duplicate criterion or claim")
        ids.add(ident); claims.add(claim)
        if (not isinstance(c["domain"], str) or c["domain"] not in DOMAINS
                or not isinstance(c["stage"], str) or c["stage"] not in REQUIRED
                or not isinstance(c["environment"], str) or c["environment"] not in ("work", "android")
                or type(c["min_passed"]) is not int or not 0 <= c["min_passed"] <= 1000000
                or c["stage"] == "syntax" and c["min_passed"] != 0):
            raise ValueError("invalid criterion scope or count")
        rows.append(deepcopy(c))
    normalized = {"contract_id": _identifier(spec["contract_id"]), "goal": _text(spec["goal"], 2000),
        "target_commit": commit, "classification": _classification(spec["classification"]),
        "criteria": sorted(rows, key=lambda c: c["id"])}
    report = {"schema_version": 1, "kind": "klone-council72-contract", "spec": normalized,
        "acceptance_policy": "all_selected_matching_runs_must_pass_each_criterion",
        "required_manifest_schema": 2, "required_clean_checkout": True,
        "require_complete_capture": True, "require_matching_packet_and_logs": True,
        "require_collector_contract_binding": True, "max_failed": 0,
        "registration_time_authenticated": False, "provenance_authenticated": False,
        "manual_review_required": True, **AUTHORITY}
    report["contract_sha256"] = hashlib.sha256(canonical(report)).hexdigest()
    if len(canonical(report)) > MAX_CONTRACT:
        raise ValueError("contract too large")
    return report


def contract_replays(report):
    try:
        return _replay_equal(report, register_contract(report["spec"]))
    except (KeyError, ValueError, TypeError, RecursionError):
        return False


def load_contract(path):
    raw = read_bounded(path, MAX_CONTRACT)
    report = json_object(raw)
    if not contract_replays(report):
        raise ValueError("contract does not replay")
    return report, hashlib.sha256(raw).hexdigest()


def template(commit):
    return {"contract_id": "klone-stage-check", "goal": "Varmenna saman commitin koko testiajo Workissa ja Androidissa.",
        "target_commit": commit, "classification": "restricted", "criteria": [
            {"id": "work-full", "claim_key": "work-full-passed", "domain": "cognition", "stage": "full", "environment": "work", "min_passed": 1},
            {"id": "android-full", "claim_key": "android-full-passed", "domain": "android", "stage": "full", "environment": "android", "min_passed": 1}]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--input", type=Path, help="unregistered criterion specification")
    choice.add_argument("--template", action="store_true")
    choice.add_argument("--verify", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home()/"klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if args.output or args.commit:
                raise ValueError("verification cannot write or replace the target commit")
            report, _ = load_contract(args.verify)
            print(json.dumps({"replay_matches": True, "contract_sha256": report["contract_sha256"],
                              "registration_time_authenticated": False}))
            return 0
        if bool(args.commit) != args.template:
            raise ValueError("--commit is required only with --template")
        spec = template(args.commit) if args.template else json_object(read_bounded(args.input, MAX_CONTRACT))
        rendered = json.dumps(register_contract(spec), ensure_ascii=False, indent=2) + '\n'
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, UnicodeError, TypeError, RecursionError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
