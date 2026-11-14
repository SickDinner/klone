"""Bind council claims to bounded original run artifacts and fixed criteria.

Uses Evidence Forensics; never executes log text, reconstructs old manifests,
writes source evidence or equates a signature with authenticated execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from .cognition_neurocortex import digest
from .council72 import AUTHORITY, SIGNALS, catalog, _replay_equal
from .council72_contract import load_contract
from .council72_review import DOMAIN_RING
from .evidence_forensics import inspect_run, _witness_inputs
from .evidence_io import checked_path, json_object, read_bounded, write_new_report

MAX_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 32 * 1024 * 1024


def _platform(row):
    env = row["environment_claim"]
    platform = env.get("platform") if isinstance(env, dict) else None
    return "android" if platform == "android" else "work" if platform in ("linux", "win32", "darwin") else "unknown"


def _case(contract, criterion, row):
    stage = row["stages"][criterion["stage"]]
    binding = (row["execution_context_claim"] or {}).get("experiment_contract")
    reason = None
    if row["commit"] != contract["spec"]["target_commit"]:
        reason = "different_or_unknown_commit"
    elif _platform(row) != criterion["environment"]:
        reason = "different_or_unknown_environment"
    elif row["manifest_schema_version"] != 2:
        reason = "v2_execution_context_required"
    elif (not binding or binding.get("contract_sha256") != contract["contract_sha256"]
          or binding.get("file_sha256") != binding.get("after_file_sha256")):
        reason = "contract_binding_missing_changed_or_different"
    elif (row["trust"]["packet_matches_source"] is not True
          or row["trust"]["execution_context_consistent"] is not True
          or row["trust"]["collection_complete"] is not True
          or row["checkout_consistent_claim"] is not True
          or row["observatory_status"]["integrity_ok"] is not True):
        reason = "incomplete_or_inconsistent_artifacts"
    elif row["contradictions"] or stage["exit_status_consistent"] is not True or stage["log_supports_claim"] is False:
        reason = "contradictory_evidence"
    elif stage["log_supports_claim"] is not True:
        reason = "log_does_not_establish_status"
    status = "unknown"
    if reason is None:
        if stage["declared_status"] == "failed":
            status, reason = "not_met", "consistent_reported_failure"
        elif criterion["min_passed"]:
            counts = stage["log_evidence"]["counts"]
            passed = counts.get("passed") if stage["log_evidence"]["framework"] == "pytest" else None
            if type(passed) is not int:
                reason = "pytest_pass_count_unavailable"
            elif passed < criterion["min_passed"]:
                status, reason = "not_met", "reported_pass_count_below_locked_minimum"
            else:
                status, reason = "met_for_review", "locally_consistent_stage_claim"
        else:
            status, reason = "met_for_review", "locally_consistent_stage_claim"
    return {"run_name": row["run_name"], "status": status, "reason": reason,
        "in_scope": (row["commit"] == contract["spec"]["target_commit"] and _platform(row) == criterion["environment"])
                    if row["commit"] is not None and _platform(row) != "unknown" else None,
        "manifest_sha256": row["manifest"].get("sha256"),
        "log_sha256": row["artifacts"][criterion["stage"] + ".log"].get("sha256"),
        "packet_sha256": row["packet"].get("packet_sha256"),
        "declared_status": stage["declared_status"], "declared_exit_code": stage["declared_exit_code"],
        "log_reported_status": stage["log_evidence"]["reported_status"],
        "counts": stage["log_evidence"]["counts"]}


def evaluate_evidence(contract_path, runs_root, run_names, *, ci_by_commit=None, attestations=None, trusted_keys=None):
    contract, file_hash = load_contract(contract_path)
    root = checked_path(runs_root, directory=True)
    if (not isinstance(run_names, list) or not 1 <= len(run_names) <= 8
            or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", n) for n in run_names)
            or len(set(run_names)) != len(run_names)):
        raise ValueError("one to eight unique run directory names required")
    _witness_inputs(attestations, trusted_keys)
    if ci_by_commit is not None and not isinstance(ci_by_commit, dict):
        raise ValueError("invalid CI snapshot map")
    if attestations is not None and (not isinstance(attestations, dict) or not isinstance(trusted_keys, dict)):
        raise ValueError("invalid explicit witness inputs")
    runs, remaining = [], MAX_SOURCE_BYTES
    for name in sorted(run_names):
        path = checked_path(root/name, directory=True)
        row, consumed = inspect_run(path, budget=remaining, ci_by_commit=ci_by_commit,
            attestation=(attestations or {}).get(name), trusted_keys=trusted_keys)
        remaining -= consumed
        runs.append(row)
    results, observations = [], []
    model = catalog()
    classification = "sealed" if contract["spec"]["classification"] == "sealed" else "restricted"
    for criterion in contract["spec"]["criteria"]:
        cases = [_case(contract, criterion, r) for r in runs]
        matching = [c for c in cases if c["in_scope"] is True]
        status = ("not_met" if any(c["status"] == "not_met" for c in matching) else
                  "met_for_review" if matching and all(c["status"] == "met_for_review" for c in matching)
                  and all(c["in_scope"] is not None for c in cases) else "unknown")
        result = {"criterion": criterion, "status": status, "matching_runs": len(matching), "cases": cases}
        results.append(result)
        ring = DOMAIN_RING[criterion["domain"]]
        king = model["rings"][ring-1]["steward_id"]
        courier = next(m["id"] for m in model["members"] if m.get("courier_for") == king)
        ident = "evidence-" + digest([contract["contract_sha256"], result])[:40]
        observations.append({"id": ident, "courier_id": courier,
            "claim_key": criterion["claim_key"], "stance": {"met_for_review": "supports", "not_met": "contradicts", "unknown": "unknown"}[status],
            "source_group": "local-artifact-claims", "source_ref": "contract:" + contract["contract_sha256"] + ":criterion:" + criterion["id"],
            "summary": f"{criterion['environment']} / {criterion['stage']}: {status}. Paikallisesti tarkistettuja raporttiväitteitä; ajon alkuperää ei ole autentikoitu.",
            "classification": classification,
            "signals": {**SIGNALS, "evidence_quality": .7 if status != "unknown" else 0.,
                        "uncertainty": .3 if status != "unknown" else 1., "risk": .8 if status == "not_met" else .5}})
    report = {"schema_version": 1, "kind": "klone-council72-evidence", "contract": contract,
        "contract_file_sha256": file_hash, "classification": classification,
        "runs": runs, "criteria": results,
        "status": "not_met" if any(r["status"] == "not_met" for r in results) else
                  "met_for_review" if all(r["status"] == "met_for_review" for r in results) else "unknown",
        "session_step_proposals": [{"observations": observations, "dispatches": []}],
        "source_independence": "all_imported_artifacts_share_one_unauthed_group",
        "history_rewritten": False, "log_commands_executed": False, "memory_write_enabled": False,
        "registration_time_authenticated": False, "origin_authenticated": False,
        "test_execution_authenticated": False, "manual_review_required": True, **AUTHORITY}
    report["evidence_sha256"] = hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if len(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError("evidence review too large")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--run", action="append", required=True, help="existing run directory basename, at most eight")
    parser.add_argument("--ci", type=Path)
    parser.add_argument("--attestations", type=Path)
    parser.add_argument("--trusted-keys", type=Path)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--output", type=Path)
    output.add_argument("--verify", type=Path, help="compare saved report against original artifacts")
    args = parser.parse_args(argv)
    try:
        kwargs = {}
        for arg, key in ((args.ci, "ci_by_commit"), (args.attestations, "attestations"), (args.trusted_keys, "trusted_keys")):
            if arg:
                kwargs[key] = json_object(read_bounded(arg, MAX_BYTES))
        report = evaluate_evidence(args.contract, args.runs_root, args.run, **kwargs)
        if args.verify:
            if not _replay_equal(json_object(read_bounded(args.verify, MAX_BYTES)), report):
                raise ValueError("report differs from current original artifacts")
        else:
            write_new_report(args.output, json.dumps(report, ensure_ascii=False, indent=2) + '\n', args.runs_root)
        print(json.dumps({"status": report["status"], "criteria": len(report["criteria"]),
                          "origin_authenticated": False, "deployment_approval": False}))
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
