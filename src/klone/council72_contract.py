"""Explicit pre-run acceptance contracts; hashes bind criteria, not chronology."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

from .acceptance_matrix import DOMAINS
from .council72 import AUTHORITY, _replay_equal, _text
from .council72_session import _identifier, _classification
from .evidence_io import checked_path, json_object, read_bounded, write_new_report
from .evidence_network import REQUIRED, SHA, HEX, canonical
from .evidence_run_context import collector_snapshot, suite_snapshot

MAX_CONTRACT = 32768


def register_contract(spec):
    fields = {"contract_id", "goal", "target_commit", "classification", "criteria"}
    if not isinstance(spec, dict) or not fields <= set(spec) or set(spec) - fields - {"execution_identity"}:
        raise ValueError("invalid contract fields")
    commit = spec["target_commit"]
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("exact target commit required")
    if not isinstance(spec["criteria"], list) or not 1 <= len(spec["criteria"]) <= 16:
        raise ValueError("one to sixteen criteria required")
    rows, ids, claims = [], set(), set()
    for c in spec["criteria"]:
        required = {"id", "claim_key", "domain", "stage", "environment", "min_passed"}
        optional = {"platform", "max_skipped", "max_deselected", "full_suite"}
        if not isinstance(c, dict) or not required <= set(c) or set(c) - required - optional:
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
        if "platform" in c and (c["platform"] not in ("linux", "win32", "darwin", "android") or
                (c["platform"] == "android") != (c["environment"] == "android")):
            raise ValueError("platform must match the criterion environment")
        for name in ("max_skipped", "max_deselected"):
            if name in c and (type(c[name]) is not int or not 0 <= c[name] <= 1000000 or c["stage"] == "syntax"):
                raise ValueError("invalid locked count limit")
        if "full_suite" in c and (c["full_suite"] is not True or c["stage"] != "full" or c.get("max_deselected",0) != 0):
            raise ValueError("full_suite requires an unfiltered full stage with zero deselection")
        rows.append(deepcopy(c))
    normalized = {"contract_id": _identifier(spec["contract_id"]), "goal": _text(spec["goal"], 2000),
        "target_commit": commit, "classification": _classification(spec["classification"]),
        "criteria": sorted(rows, key=lambda c: c["id"])}
    if "execution_identity" in spec:
        identity = spec["execution_identity"]
        if (not isinstance(identity,dict) or set(identity) != {"test_suite_sha256","collector_sha256"} or
                any(not isinstance(v,str) or not HEX.fullmatch(v) for v in identity.values())):
            raise ValueError("invalid locked suite or collector identity")
        normalized["execution_identity"] = deepcopy(identity)
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


def lock_checkout(spec, root):
    """Capture suite/collector identity from an explicitly selected clean checkout."""
    register_contract(spec)
    root = checked_path(Path(root),directory=True)
    def git(*args):
        return subprocess.check_output(["git","-C",str(root),*args],timeout=15).decode("utf-8").strip()
    if git("status","--porcelain") or git("rev-parse","HEAD") != spec["target_commit"]:
        raise ValueError("lock-checkout requires a clean checkout at the exact target commit")
    result = deepcopy(spec)
    result["execution_identity"] = {"test_suite_sha256":suite_snapshot(root)["sha256"],
                                    "collector_sha256":collector_snapshot(root)}
    if git("status","--porcelain") or git("rev-parse","HEAD") != spec["target_commit"]:
        raise ValueError("checkout changed while locking identity")
    return register_contract(result)


def validate_checkout(contract, *, commit, suite_sha256, collector_sha256, platform, clean):
    """Optional stronger identity gate, invoked before output reservation/stages."""
    identity = contract["spec"].get("execution_identity")
    if identity is None:
        return
    environment = "android" if platform == "android" else "work" if platform in ("linux","win32","darwin") else None
    eligible = any(c["environment"] == environment and c.get("platform",platform) == platform
                   for c in contract["spec"]["criteria"])
    if (clean is not True or commit != contract["spec"]["target_commit"] or not eligible or
            identity != {"test_suite_sha256":suite_sha256,"collector_sha256":collector_sha256}):
        raise ValueError("checkout, suite, collector or platform differs from locked contract")


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
    parser.add_argument("--lock-checkout",type=Path,help="pin suite and collector from a clean target checkout")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home()/"klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if args.output or args.commit or args.lock_checkout:
                raise ValueError("verification cannot write or replace the target commit")
            report, _ = load_contract(args.verify)
            print(json.dumps({"replay_matches": True, "contract_sha256": report["contract_sha256"],
                              "registration_time_authenticated": False}))
            return 0
        if bool(args.commit) != args.template:
            raise ValueError("--commit is required only with --template")
        spec = template(args.commit) if args.template else json_object(read_bounded(args.input, MAX_CONTRACT))
        report = lock_checkout(spec,args.lock_checkout) if args.lock_checkout else register_contract(spec)
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, UnicodeError, TypeError, RecursionError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
