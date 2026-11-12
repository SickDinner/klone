"""Deterministic offline forensics of original KLONE evidence.

Reads bounded snapshots, composes existing quality/recovery/history/graph/dossier
contracts, and writes reports only outside the historical input tree. A parsed
log, local hash, matching packet or exported CI claim never grants provenance
or deployment authority. No input commands are executed and no network is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path

from klone.evidence_artifact_inspector import snapshot
from klone.evidence_cross_environment import compare as compare_ci
from klone.evidence_decision_dossier import build as build_dossier
from klone.evidence_io import (EvidenceIOError, checked_path, json_object,
                               output_path, read_bounded, write_report)
from klone.evidence_log_analysis import analyze as analyze_log
from klone.evidence_network import (REQUIRED, STAGES, MAX_LOG, HEX, SHA,
                                    assemble_packet, canonical, validate_run)
from klone.evidence_observatory import compare_history
from klone.evidence_quality import CATEGORIES, classify
from klone.evidence_recovery_planner import plan as recovery_plan
from klone.evidence_regression_graph import graph

MAX_PACKET = 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_RUNS = 1000
MAX_DIRECTORY_ENTRIES = 128
MAX_CI = 2 * 1024 * 1024
KIND = "klone-evidence-forensics"


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _manifest(raw: bytes | None) -> tuple[dict | None, bool, list[str]]:
    if raw is None:
        return None, False, ["manifest_unreadable_or_missing"]
    try:
        data = json_object(raw)
    except (ValueError, UnicodeError, RecursionError):
        return None, False, ["manifest_invalid_json"]
    try:
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise ValueError("schema")
        before, after, stages = data["before"], data["after"], data["stages"]
        if not all(isinstance(value, dict) for value in (before, after, stages)):
            raise ValueError("nested object")
        if any(not isinstance(stages.get(name), dict) for name in STAGES):
            raise ValueError("stage object")
        for name in STAGES:
            code = stages[name].get("exit_code")
            if code is not None and type(code) is not int:
                raise ValueError("exit code")
        validate_run(data)
        start, end = _timestamp(data.get("started_at")), _timestamp(data.get("completed_at"))
        if start is None or end is None or start > end:
            raise ValueError("time order")
        return data, True, []
    except (ValueError, KeyError, TypeError, AttributeError):
        return data, False, ["manifest_invalid_schema_or_claims"]


def _all_known(values) -> bool | None:
    values = list(values)
    return False if any(v is False for v in values) else True if all(v is True for v in values) else None


def _artifact_state(meta: dict) -> dict:
    state = meta.get("state", "unknown")
    exists = (False if state == "missing" else True if state in
              ("present", "oversized", "budget_exceeded", "symlink_rejected", "not_regular") else None)
    return {**meta, "exists": exists, "readable": True if state == "present" else False if state == "unreadable" else None,
            "empty": meta.get("bytes") == 0 if state == "present" else None}


def _select_packet(directory: Path) -> tuple[str | None, list[str]]:
    conventional = directory / "evidence-packet.json"
    if conventional.exists() or conventional.is_symlink():
        return conventional.name, []
    candidates = []
    count = 0
    for path in directory.iterdir():
        count += 1
        if count > MAX_DIRECTORY_ENTRIES:
            return None, ["artifact_directory_entry_limit"]
        if "packet" in path.name.lower() and path.suffix == ".json":
            candidates.append(path.name)
    if len(candidates) > 1:
        return None, ["ambiguous_packet_candidates"]
    return (candidates[0] if candidates else "evidence-packet.json"), []


def _packet(directory: Path, manifest: dict | None, manifest_valid: bool,
            contents: dict[str, bytes], artifacts: dict, budget: int) -> tuple[dict, int]:
    name, errors = _select_packet(directory)
    result = {"filename": name, "state": "unknown" if errors else "missing",
              "exists": None, "readable": None, "structure_valid": None, "matches_source": None, "sha256": None,
              "packet_sha256": None, "errors": errors}
    if name is None:
        return result, 0
    try:
        raw = read_bounded(directory / name, min(MAX_PACKET, max(0, budget)))
    except EvidenceIOError as exc:
        result["state"] = ("budget_exceeded" if exc.code == "oversized" and
                           exc.size is not None and exc.size <= MAX_PACKET else exc.code)
        result["exists"] = False if result["state"] == "missing" else True if result["state"] in ("oversized", "symlink_rejected", "not_regular", "budget_exceeded") else None
        result["readable"] = False if result["state"] == "unreadable" else None
        result["errors"].append("packet_unreadable:" + result["state"])
        return result, 0
    result.update(state="present", exists=True, readable=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    try:
        packet = json_object(raw)
        digest = packet.get("packet_sha256")
        packet_files = packet.get("files")
        if (type(packet.get("schema_version")) is not int or packet["schema_version"] != 1
                or packet.get("kind") != "klone-evidence-packet"
                or not isinstance(digest, str) or not HEX.fullmatch(digest)
                or not isinstance(packet.get("commit"), str) or not SHA.fullmatch(packet["commit"])
                or not isinstance(packet_files, dict)
                or set(packet_files) != {name + ".log" for name in STAGES}):
            raise ValueError("packet schema")
        for entry in packet_files.values():
            if (not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str)
                    or not HEX.fullmatch(entry["sha256"]) or type(entry.get("bytes")) is not int
                    or not 0 <= entry["bytes"] <= MAX_LOG):
                raise ValueError("packet artifact schema")
        packet_stages = packet.get("stages")
        if (not isinstance(packet.get("run_json_sha256"), str)
                or not HEX.fullmatch(packet["run_json_sha256"])
                or not isinstance(packet_stages, dict) or set(packet_stages) != set(STAGES)
                or any(packet_stages[n] not in ("passed", "failed") for n in REQUIRED)
                or packet_stages["torch_probe"] not in ("passed", "failed", "unavailable", "not_present")
                or _timestamp(packet.get("observed_at")) is None
                or packet.get("overall") not in ("passed", "failed")
                or packet.get("device_identity_verified") is not False
                or packet.get("deployment_approval") is not False
                or packet.get("origin_authentication") != "not_provided"):
            raise ValueError("packet claims schema")
        result["structure_valid"] = True
        result["packet_sha256"] = digest
        actual_digest = hashlib.sha256(canonical({k: v for k, v in packet.items()
                                                   if k != "packet_sha256"})).hexdigest()
        if actual_digest != digest:
            result["matches_source"] = False
            result["errors"].append("packet_digest_mismatch")
        elif manifest_valid and all(n + ".log" in contents for n in STAGES):
            files = {n + ".log": {"sha256": artifacts[n + ".log"]["sha256"],
                                     "bytes": artifacts[n + ".log"]["bytes"]} for n in STAGES}
            expected = assemble_packet(manifest, artifacts["run.json"]["sha256"], files)
            result["matches_source"] = packet == expected
            if packet != expected:
                result["errors"].append("packet_source_mismatch")
        else:
            result["errors"].append("packet_source_comparison_unavailable")
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError, RecursionError):
        result["structure_valid"] = False
        result["errors"].append("packet_invalid_json_or_schema")
    return result, len(raw)


def _stage_claims(manifest: dict | None, contents: dict[str, bytes]) -> tuple[dict, list[str]]:
    raw_stages = manifest.get("stages") if isinstance(manifest, dict) else None
    raw_stages = raw_stages if isinstance(raw_stages, dict) else {}
    result, contradictions = {}, []
    for name in STAGES:
        claimed = raw_stages.get(name)
        claimed = claimed if isinstance(claimed, dict) else {}
        status, code = claimed.get("status"), claimed.get("exit_code")
        status = status if status in ("passed", "failed", "not_present", "unavailable") else "unknown"
        code = code if type(code) is int else None
        exit_consistent = None
        if status in ("passed", "failed") and code is not None:
            exit_consistent = (status == "passed") == (code == 0)
            if not exit_consistent:
                contradictions.append(name + ":exit_status_mismatch")
        raw = contents.get(name + ".log")
        evidence = (analyze_log(raw, name) if raw is not None else
                    {"reported_status": "unknown", "reason": "log_unreadable_or_missing",
                     "summary": None, "counts": {}, "empty": None,
                     "execution_authenticated": False})
        observed = evidence["reported_status"]
        known = ("passed", "failed", "not_present", "unavailable")
        support = status == observed if status in known and observed in known else None
        if support is False:
            contradictions.append(name + ":manifest_" + status + "_log_" + observed)
        result[name] = {"declared_status": status, "declared_exit_code": code,
                        "exit_status_consistent": exit_consistent,
                        "log_evidence": evidence, "log_supports_claim": support}
    return result, contradictions


def _ci(commit: str | None, status: dict, snapshots: dict) -> tuple[dict, dict]:
    candidate = snapshots.get(commit) if commit else None
    candidate = candidate if isinstance(candidate, dict) else None
    if candidate is None:
        comparison = {"consistent_claims": None, "errors": ["github_ci_unavailable"],
                      "origin_authenticated": False, "deployment_approval": False}
        return {"state": "unavailable", "commit": None, "conclusion": None,
                "origin_authenticated": False}, comparison
    normalized = {key: candidate.get(key) for key in
                  ("commit", "conclusion", "workflow", "run_id", "run_status")}
    comparison = compare_ci(status, normalized)
    return {**normalized, "state": "reported_success" if normalized["conclusion"] == "success"
            else "reported_failure" if normalized["conclusion"] in
            ("failure", "cancelled", "timed_out", "action_required") else "unknown",
            "origin_authenticated": False}, comparison


def _recovery(root: Path, name: str, category: str) -> dict:
    if category == "incomplete":
        try:
            planned = recovery_plan(root, [{"run_name": name, "category": category}])["runs"]
            if planned:
                return planned[0]
        except (ValueError, OSError):
            pass
    return {"run_name": name, "action": "investigate_content_mismatch" if category == "contradictory"
            else "review_unverified_provenance" if category == "verified" else "inspect_source_artifacts",
            "recommendation": "Inspect original inputs read-only; never recreate historical provenance.",
            "historical_evidence_recreated": False}


def inspect_run(directory: Path, *, budget: int = MAX_TOTAL_BYTES,
                ci_by_commit: dict | None = None) -> tuple[dict, int]:
    inventory, contents = snapshot(directory, byte_budget=budget)
    artifacts = {name: _artifact_state(meta) for name, meta in inventory["artifacts"].items()}
    consumed = sum(len(raw) for raw in contents.values())
    manifest, valid, manifest_errors = _manifest(contents.get("run.json"))
    artifacts["run.json"]["structure_valid"] = valid if "run.json" in contents else None
    packet, packet_bytes = _packet(directory, manifest, valid, contents, artifacts, budget - consumed)
    stages, contradictions = _stage_claims(manifest, contents)
    if packet["matches_source"] is False:
        contradictions.append("packet:source_or_digest_mismatch")
    errors = [*inventory["errors"], *manifest_errors, *packet["errors"]]
    integrity = valid and packet["matches_source"] is True
    status_errors = []
    if not valid or any(n + ".log" not in contents for n in STAGES):
        status_errors.append("run_invalid:bounded_snapshot_incomplete")
    if packet["state"] != "present" or packet["structure_valid"] is not True:
        status_errors.append("packet_unreadable:bounded_snapshot_unavailable")
    if packet["matches_source"] is False:
        status_errors.append("packet_mismatch")
    elif packet["matches_source"] is None and not status_errors:
        status_errors.append("run_invalid:source_comparison_unavailable")
    commit = manifest.get("before", {}).get("commit") if valid else None
    reported_passed = (all(stages[n]["declared_status"] == "passed" for n in REQUIRED)
                       if valid else None)
    status = {"run_name": directory.name, "commit": commit,
              "integrity_ok": bool(integrity),
              "required_stages_passed": reported_passed is True,
              "stage_statuses": {n: stages[n]["declared_status"] if valid else "unknown" for n in STAGES},
              "packet_sha256": packet.get("packet_sha256"), "errors": status_errors,
              "origin_authenticated": False, "deployment_approval": False}
    quality = classify(status)
    if contradictions:
        quality = {**quality, "category": "contradictory", "reason": "explicit_claim_contradiction"}
    github, comparison = _ci(commit, status, ci_by_commit or {})
    dossier = build_dossier({"local": status, "github": github, "comparison": comparison})
    environment = manifest.get("environment") if valid else None
    if not isinstance(environment, (str, dict)) or not environment:
        environment = None
    return {
        "run_name": directory.name, "commit": commit,
        "manifest": artifacts["run.json"], "packet": packet, "artifacts": artifacts,
        "stages": stages, "quality": quality, "contradictions": contradictions,
        "errors": sorted(set(errors)), "observatory_status": status,
        "recovery": _recovery(directory.parent, directory.name, quality["category"]),
        "github": github, "github_comparison": comparison, "decision_dossier": dossier,
        "completed_at_claim": manifest.get("completed_at") if valid else None,
        "environment_claim": environment,
        "trust": {"manifest_and_logs_found": _all_known(a["exists"] for a in artifacts.values()),
                  "manifest_and_logs_readable": _all_known(a["readable"] for a in artifacts.values()),
                  "manifest_structurally_valid": valid if "run.json" in contents else None,
                  "packet_matches_source": packet["matches_source"],
                  "manifest_reports_required_stages_passed": reported_passed,
                  "all_required_logs_support_claims": _all_known(stages[n]["log_supports_claim"] for n in REQUIRED),
                  "origin_authenticated": False, "test_execution_authenticated": False,
                  "deployment_approval": False},
        "origin_authenticated": False, "deployment_approval": False,
    }, consumed + packet_bytes


def _comparisons(runs: list[dict]) -> list[dict]:
    by_name = {run["run_name"]: run for run in runs}
    result = []
    for comparison in compare_history([run["observatory_status"] for run in runs]):
        before, after = by_name[comparison["from_run"]], by_name[comparison["to_run"]]
        t0, t1 = _timestamp(before["completed_at_claim"]), _timestamp(after["completed_at_claim"])
        temporal = t0 is not None and t1 is not None and t0 < t1
        environment = (before["environment_claim"] is not None
                       and before["environment_claim"] == after["environment_claim"])
        comparable = comparison["comparable"] and temporal and environment
        regressed, recovered = [], []
        unknown = set(comparison["unknown_transitions"])
        if not comparison["comparable"]:
            unknown.update(REQUIRED)
        for name in REQUIRED:
            a, b = before["stages"][name], after["stages"][name]
            content = (a["log_supports_claim"] is True and b["log_supports_claim"] is True
                       and a["exit_status_consistent"] is True and b["exit_status_consistent"] is True)
            if comparable and content and not before["contradictions"] and not after["contradictions"]:
                if name in comparison["regressed_stages"]:
                    regressed.append(name)
                if name in comparison["recovered_stages"]:
                    recovered.append(name)
            elif a["declared_status"] != b["declared_status"] or name in comparison["regressed_stages"]:
                unknown.add(name)
        result.append({**comparison, "comparable": bool(comparable),
                       "regressed_stages": regressed, "recovered_stages": recovered,
                       "unknown_transitions": sorted(unknown),
                       "environment_claims_match": environment, "time_claims_ordered": temporal,
                       "ordering": "directory_name_only", "causality_established": False,
                       "confirmation_scope": "locally_consistent_claims_only",
                       "origin_authenticated": False, "deployment_approval": False})
    return result


def generate(runs_root: Path, *, ci_by_commit: dict | None = None,
             byte_budget: int = MAX_TOTAL_BYTES, max_runs: int = MAX_RUNS) -> dict:
    root = checked_path(runs_root, directory=True)
    if type(byte_budget) is not int or not 0 <= byte_budget <= MAX_TOTAL_BYTES:
        raise ValueError("invalid aggregate byte budget")
    if type(max_runs) is not int or not 1 <= max_runs <= MAX_RUNS:
        raise ValueError("invalid run limit")
    if ci_by_commit is not None and not isinstance(ci_by_commit, dict):
        raise ValueError("CI snapshot must be a commit mapping")
    directories, rejected = [], []
    entry_count = 0
    for path in root.iterdir():
        entry_count += 1
        if entry_count > max_runs:
            raise ValueError("run count limit exceeded")
        if path.is_symlink():
            rejected.append({"name": path.name, "reason": "symlink_rejected"})
        elif path.is_dir():
            directories.append(path)
        if len(directories) + len(rejected) > max_runs:
            raise ValueError("run count limit exceeded")
    runs, consumed = [], 0
    for directory in sorted(directories):
        try:
            run, used = inspect_run(directory, budget=byte_budget - consumed,
                                    ci_by_commit=ci_by_commit)
        except (ValueError, OSError) as exc:
            rejected.append({"name": directory.name, "reason": "unsafe_or_unreadable_directory"})
            continue
        consumed += used
        runs.append(run)
    statuses = [run["observatory_status"] for run in runs]
    comparisons = _comparisons(runs)
    categories = Counter(run["quality"]["category"] for run in runs)
    recovery = Counter(run["recovery"]["action"] for run in runs)
    regression_graph = graph(statuses)
    # Keep the established graph contract, but suppress unconfirmed transitions.
    confirmed = {(c["to_run"], stage) for c in comparisons for stage in c["regressed_stages"]}
    allowed_nodes = set()
    for node in regression_graph["nodes"]:
        if node["kind"] != "regression":
            allowed_nodes.add(node["id"])
        else:
            index = int(node["id"].split(":")[1])
            if (runs[index]["run_name"], node["label"]) in confirmed:
                allowed_nodes.add(node["id"])
    regression_graph["nodes"] = [n for n in regression_graph["nodes"] if n["id"] in allowed_nodes]
    regression_graph["edges"] = [e for e in regression_graph["edges"]
                                 if e["from"] in allowed_nodes and e["to"] in allowed_nodes]
    result = {"schema_version": 1, "kind": KIND, "runs": runs,
              "categories": {name: categories[name] for name in CATEGORIES},
              "comparisons": comparisons, "regression_graph": regression_graph,
              "confirmed_regression_transitions": sum(len(c["regressed_stages"]) for c in comparisons),
              "unknown_transition_count": sum(len(c["unknown_transitions"]) for c in comparisons),
              "recovery_counts": dict(sorted(recovery.items())), "rejected_entries": sorted(rejected, key=lambda x: x["name"]),
              "limits": {"max_runs": max_runs, "max_total_bytes": byte_budget,
                         "bytes_read": consumed, "max_log_bytes": MAX_LOG},
              "source_policy": {"read_only": True, "network_used": False,
                                "historical_evidence_recreated": False},
              "origin_authenticated": False, "deployment_approval": False,
              "note": "Verified means local snapshot consistency only. Log text, directory order and hashes do not authenticate historical execution."}
    result["analysis_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def render(report: dict) -> str:
    """Use the same offline renderer as Mission Control, with escaped embedded JSON."""
    static = Path(__file__).parent / "static"
    page = (static / "evidence.html").read_text(encoding="utf-8")
    script = (static / "evidence-view.js").read_text(encoding="utf-8")
    encoded = json.dumps(report, sort_keys=True, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = page.replace('<nav><a href="/">Mission Control</a></nav>', '<nav>KLONE · paikallinen tutkimusraportti</nav>')
    page = page.replace("script-src 'self'", "script-src 'unsafe-inline'")
    return page.replace('<script src="/static/evidence-view.js" defer></script>',
                        '<script id="initial-evidence" type="application/json">' + encoded +
                        '</script><script>' + script + '</script>')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--html-output", type=Path)
    parser.add_argument("--github-ci", type=Path, help="Offline commit-keyed CI export; no network calls")
    args = parser.parse_args(argv)
    try:
        root = checked_path(args.runs_root, directory=True)
        destinations = [args.json_output] + ([args.html_output] if args.html_output else [])
        normalized = [output_path(path, root) for path in destinations]
        if len(set(normalized)) != len(normalized):
            raise ValueError("report destinations must be distinct")
        ci = json_object(read_bounded(args.github_ci, MAX_CI)) if args.github_ci else None
        if args.github_ci and checked_path(args.github_ci) in normalized:
            raise ValueError("report output must not overwrite the CI input")
        result = generate(root, ci_by_commit=ci)
        rendered = render(result) if args.html_output else None
        write_report(args.json_output, json.dumps(result, indent=2, sort_keys=True) + "\n", root)
        if args.html_output:
            write_report(args.html_output, rendered, root)
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    print(json.dumps({"runs": len(result["runs"]), "categories": result["categories"],
                      "confirmed_regressions": result["confirmed_regression_transitions"],
                      "unknown_transitions": result["unknown_transition_count"],
                      "analysis_sha256": result["analysis_sha256"],
                      "origin_authenticated": False, "deployment_approval": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
