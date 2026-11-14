"""Predeclared battery criteria and file-backed Council 72 result observations.

The battery binds a contract digest before running stages. Hashes preserve the
selected criteria; they do not authenticate execution, identity or chronology.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys

from .cognition_neurocortex import digest
from .council72 import AUTHORITY, _replay_equal
from .council72_briefing import build_briefing
from .council72_session import MAX_BYTES
from .evidence_forensics import inspect_run
from .evidence_io import checked_path, json_object, output_path, read_bounded, write_new_report
from .evidence_network import REQUIRED
from .evidence_run_context import collector_snapshot, suite_snapshot

PLATFORMS = ("linux", "win32", "android")
FULL_COMMAND = ["-B", "-m", "pytest", "-p", "no:cacheprovider", "-q"]


def _hex(value, length):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{" + str(length) + "}", value):
        raise ValueError("invalid experiment identity digest")
    return value


def _identity(identity):
    fields = {"commit", "test_suite_sha256", "collector_sha256", "platform"}
    if not isinstance(identity, dict) or set(identity) != fields:
        raise ValueError("all experiment identity fields required")
    _hex(identity["commit"], 40)
    for key in ("test_suite_sha256", "collector_sha256"):
        _hex(identity[key], 64)
    if identity["platform"] not in PLATFORMS or type(identity["platform"]) is not str:
        raise ValueError("unsupported experiment platform")
    return dict(identity)


def capture_identity(root, *, platform=None):
    """Explicit CLI preparation only. Git is read with fixed argv, never a shell."""
    root = checked_path(Path(root), directory=True)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], timeout=15).decode("utf-8").strip()
    if git("status", "--porcelain"):
        raise ValueError("prepare the contract from a clean checkout")
    before = git("rev-parse", "HEAD")
    identity = _identity({"commit": before, "test_suite_sha256": suite_snapshot(root)["sha256"],
                          "collector_sha256": collector_snapshot(root), "platform": platform or sys.platform})
    if git("rev-parse", "HEAD") != before or git("status", "--porcelain"):
        raise ValueError("checkout changed during contract preparation")
    return identity


def build_contract(briefing, task_id, identity, *, minimum_full_passed=1, maximum_full_skipped=0):
    identity = _identity(identity)
    for name, value, lower, upper in (("minimum_full_passed", minimum_full_passed, 1, 1000000),
                                      ("maximum_full_skipped", maximum_full_skipped, 0, 10000)):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"invalid {name}")
    if not isinstance(briefing, dict) or not isinstance(briefing.get("review"), dict):
        raise ValueError("a replayable briefing is required")
    canonical = build_briefing(briefing["review"])
    if not _replay_equal(briefing, canonical):
        raise ValueError("briefing must replay before preparing a contract")
    task = next((t for t in canonical["review"]["plan"]["tasks"] if t["id"] == task_id), None)
    if task is None or task["kind"] != "development_check" or task["allocation"] != "selected":
        raise ValueError("select one budgeted development_check task")
    contract = {"schema_version": 1, "kind": "klone-council72-experiment-contract",
        "briefing": canonical, "briefing_sha256": canonical["briefing_sha256"],
        "task_id": task_id, "domain": task["domain"], "route": deepcopy(task["route"]),
        "classification": canonical["classification"], "expected": identity,
        "acceptance": {"required_stages": list(REQUIRED), "minimum_full_passed": minimum_full_passed,
                       "maximum_full_skipped": maximum_full_skipped},
        "claim_scope": "battery_criteria_only_not_domain_completion",
        "predeclaration": "digest_selected_by_runner_before_stages_no_trusted_timestamp",
        "execution_enabled": False, "provenance_authenticated": False, **AUTHORITY}
    contract["contract_sha256"] = digest(contract)
    _bounded(contract)
    return contract


def _canonical_contract(contract):
    criteria = contract["acceptance"]
    return build_contract(contract["briefing"], contract["task_id"], contract["expected"],
        minimum_full_passed=criteria["minimum_full_passed"], maximum_full_skipped=criteria["maximum_full_skipped"])


def contract_replays(contract):
    try:
        return _replay_equal(contract, _canonical_contract(contract))
    except (KeyError, ValueError, TypeError, RecursionError, OverflowError):
        return False


def validate_run_identity(contract, *, commit, suite_sha256, collector_sha256, platform, clean):
    """Called by the collector before reserving output or executing a test."""
    if not contract_replays(contract):
        raise ValueError("experiment contract does not replay")
    actual = {"commit": commit, "test_suite_sha256": suite_sha256,
              "collector_sha256": collector_sha256, "platform": platform}
    if actual != contract["expected"] or clean is not True:
        raise ValueError("checkout, suite, collector or platform does not match experiment contract")
    return contract["contract_sha256"]


def _bounded(value):
    rendered = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(rendered.encode("utf-8")) > MAX_BYTES:
        raise ValueError("experiment report too large")
    return rendered


def _assessment(contract, forensic):
    expected = contract["expected"]
    execution = forensic.get("execution_context_claim") or {}
    environment = forensic.get("environment_claim") or {}
    environment = environment if isinstance(environment, dict) else {}
    trust = forensic["trust"]
    checks = []
    def check(name, actual, wanted):
        state = "unknown" if actual is None else "passed" if _replay_equal(actual, wanted) else "failed"
        checks.append({"criterion": name, "expected": wanted, "observed": actual, "status": state})
    check("contract_digest", forensic.get("experiment_contract_sha256_claim"), contract["contract_sha256"])
    check("commit", forensic["commit"], expected["commit"])
    check("platform", environment.get("platform"), expected["platform"])
    check("manifest_v2", forensic["manifest_schema_version"], 2)
    check("source_packet_matches", trust["packet_matches_source"], True)
    check("clean_checkout", forensic.get("checkout_consistent_claim"), True)
    check("context_consistent", trust["execution_context_consistent"], True)
    check("complete_capture", trust["collection_complete"], True)
    for position in ("before", "after"):
        suite = execution.get("test_suite_" + position) or {}
        check("suite_" + position, suite.get("sha256"), expected["test_suite_sha256"])
    check("collector_before", execution.get("collector_sha256"), expected["collector_sha256"])
    check("collector_after", execution.get("collector_after_sha256"), expected["collector_sha256"])
    command = (execution.get("commands") or {}).get("full")
    check("unfiltered_full_pytest_command", command[1:] if isinstance(command, list) else None, FULL_COMMAND)
    check("consistent_source_claims", not forensic["contradictions"] if trust["manifest_structurally_valid"] is True else None, True)
    binding = ("mismatch" if any(c["status"] == "failed" for c in checks) else
               "matched" if all(c["status"] == "passed" for c in checks) else "unknown")
    criteria = []
    for stage in contract["acceptance"]["required_stages"]:
        entry = forensic["stages"][stage]
        declared, observed = entry["declared_status"], entry["log_evidence"]["reported_status"]
        state = ("failed" if declared == "failed" and observed == "failed" else
                 "passed" if declared == "passed" and observed == "passed" and entry["declared_exit_code"] == 0 else "unknown")
        criteria.append({"criterion": "stage:" + stage, "expected": "passed", "observed": observed, "status": state})
    full = forensic["stages"]["full"]["log_evidence"]
    counts = full["counts"]
    # Test counts are only comparable for a recognized pytest summary.
    for name, observed, limit, direction in (
        ("minimum_full_passed", counts.get("passed"), contract["acceptance"]["minimum_full_passed"], "minimum"),
        ("maximum_full_skipped", counts.get("skipped", 0) if full.get("framework") == "pytest" else None,
         contract["acceptance"]["maximum_full_skipped"], "maximum"),
        ("maximum_full_deselected", counts.get("deselected", 0) if full.get("framework") == "pytest" else None,
         0, "maximum")):
        state = ("unknown" if full.get("framework") != "pytest" or type(observed) is not int else
                 "passed" if (observed >= limit if direction == "minimum" else observed <= limit) else "failed")
        criteria.append({"criterion": name, "expected": limit, "observed": observed, "status": state})
    outcome = ("indeterminate" if binding != "matched" else
               "criteria_failed" if any(c["status"] == "failed" for c in criteria) else
               "criteria_met" if all(c["status"] == "passed" for c in criteria) else "indeterminate")
    stance = {"criteria_met": "supports", "criteria_failed": "contradicts", "indeterminate": "unknown"}[outcome]
    manifest_hash = forensic["manifest"].get("sha256")
    source = {"manifest_sha256": manifest_hash,
              "packet_sha256": forensic["packet"].get("packet_sha256"),
              "log_sha256": {n: forensic["artifacts"][n + ".log"].get("sha256") for n in REQUIRED},
              "quality": forensic["quality"]["category"], "contradictions": list(forensic["contradictions"]),
              "origin_authenticated": False, "test_execution_authenticated": False}
    source_id = digest([contract["contract_sha256"], source])
    observation = {"id": "experiment-" + source_id[:40], "courier_id": contract["route"]["courier_id"],
        "source_ref": "run-manifest-sha256:" + (manifest_hash or "unavailable"),
        "source_group": "klone-test-evidence", "claim_key": "experiment-" + contract["contract_sha256"][:40],
        "stance": stance, "classification": contract["classification"],
        "summary": "Koesopimuksen " + contract["task_id"] + " testikriteerien tulos: " + outcome +
                   ". Tulos perustuu paikallisiin tiedostoihin; ajon alkuperää ei ole autentikoitu."}
    report = {"schema_version": 1, "kind": "klone-council72-experiment-evaluation", "contract": deepcopy(contract),
        "contract_sha256": contract["contract_sha256"], "classification": contract["classification"],
        "binding_status": binding, "outcome": outcome, "identity_checks": checks, "acceptance_checks": criteria,
        "source": source, "observation": observation, "source_independence": "single_klone_test_evidence_group",
        "manual_review_required": True, "execution_enabled": False, "provenance_authenticated": False,
        "chronology_authenticated": False, **AUTHORITY}
    report["evaluation_sha256"] = digest(report)
    _bounded(report)
    return report


def evaluate_contract(contract, run_directory):
    try:
        canonical = _canonical_contract(contract)
    except (KeyError, TypeError) as exc:
        raise ValueError("experiment contract does not replay") from exc
    if not _replay_equal(contract, canonical):
        raise ValueError("experiment contract does not replay")
    directory = checked_path(Path(run_directory), directory=True)
    forensic, _ = inspect_run(directory)
    return _assessment(canonical, forensic)


def evaluation_matches_sources(report, run_directory):
    try:
        return _replay_equal(report, evaluate_contract(report["contract"], run_directory))
    except (KeyError, ValueError, TypeError, OSError, RecursionError, OverflowError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--prepare-briefing", type=Path)
    choice.add_argument("--evaluate-contract", type=Path)
    choice.add_argument("--verify-contract", type=Path)
    choice.add_argument("--verify-evaluation", type=Path)
    parser.add_argument("--task")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--platform", choices=PLATFORMS)
    parser.add_argument("--minimum-full-passed", type=int, default=1)
    parser.add_argument("--maximum-full-skipped", type=int, default=0)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home()/"klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        selected = args.prepare_briefing or args.evaluate_contract or args.verify_contract or args.verify_evaluation
        data = json_object(read_bounded(selected, MAX_BYTES))
        if args.verify_contract or args.verify_evaluation:
            if args.output:
                raise ValueError("verification cannot write output")
            if args.verify_evaluation and args.run_dir is None:
                raise ValueError("evaluation verification requires --run-dir with original sources")
            okay = evaluation_matches_sources(data, args.run_dir) if args.verify_evaluation else contract_replays(data)
            if not okay:
                raise ValueError("experiment does not replay or sources changed")
            print(json.dumps({"kind": "klone-council72-experiment-check", "replay_matches": True,
                "scope": "original_sources_compared" if args.verify_evaluation else "contract_replay_only",
                "provenance_authenticated": False, **AUTHORITY}))
            return 0
        if args.prepare_briefing:
            if not args.task or args.run_dir:
                raise ValueError("preparation requires --task and does not read a run")
            report = build_contract(data, args.task, capture_identity(args.root, platform=args.platform),
                minimum_full_passed=args.minimum_full_passed, maximum_full_skipped=args.maximum_full_skipped)
        else:
            if not args.run_dir:
                raise ValueError("evaluation requires --run-dir")
            report = evaluate_contract(data, args.run_dir)
        rendered = _bounded(report)
        if args.output:
            if args.run_dir:
                output_path(args.output, args.run_dir)
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
