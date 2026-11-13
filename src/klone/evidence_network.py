"""KLONE Evidence Network v1: offline manifests, independent anchors and triage.

Integrity checks do not establish the identity of a device or runner.
No secrets, network access, deployment decisions or repository writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from klone.evidence_run_context import validate_context

STAGES = ("syntax", "cognition", "full", "local_deploy", "torch_probe")
REQUIRED = STAGES[:4]
SHA = re.compile(r"^[0-9a-f]{40}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_LOG = 16 * 1024 * 1024


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _time(value: str) -> None:
    if not isinstance(value, str):
        raise ValueError("invalid timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")


def _read_json(path: Path, limit: int = 65536) -> dict:
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("missing or oversized JSON: " + path.name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON object required")
    return data


def validate_run(run: dict) -> None:
    if type(run.get("schema_version")) is not int or run["schema_version"] not in (1, 2):
        raise ValueError("unsupported battery schema")
    before, after = run["before"], run["after"]
    commit = before["commit"]
    if not isinstance(commit, str) or not SHA.fullmatch(commit) or after["commit"] != commit:
        raise ValueError("invalid or changed commit")
    stages = run["stages"]
    if set(stages) != set(STAGES):
        raise ValueError("stage set mismatch")
    for name in REQUIRED:
        stage = stages[name]
        if stage.get("status") not in ("passed", "failed"):
            raise ValueError("invalid required stage")
        if (stage["status"] == "passed") != (stage.get("exit_code") == 0):
            raise ValueError("contradictory required stage")
    optional = stages["torch_probe"]
    if optional.get("status") not in ("passed", "failed", "unavailable", "not_present"):
        raise ValueError("invalid optional stage")
    required_ok = all(stages[n]["status"] == "passed" for n in REQUIRED)
    consistent = (before.get("dirty") is False and after.get("dirty") is False)
    execution_ok = True
    if run["schema_version"] == 2:
        execution = validate_context(run)
        execution_ok = execution["context_consistent"] and run["collection_complete"]
    if (run.get("required_tests_passed") is not required_ok
            or run.get("checkout_consistent") is not consistent
            or run.get("overall") != ("passed" if required_ok and consistent and execution_ok else "failed")):
        raise ValueError("contradictory run verdict")
    if run.get("device_identity_verified") is not False or run.get("deployment_approval") is not False:
        raise ValueError("unsupported authenticity or approval claim")
    _time(run["started_at"])
    _time(run["completed_at"])


def build_packet(directory: Path) -> dict:
    run_path = directory / "run.json"
    run = _read_json(run_path)
    validate_run(run)
    files = {}
    for stage in STAGES:
        path = directory / (stage + ".log")
        if not path.is_file() or path.stat().st_size > MAX_LOG:
            raise ValueError("missing or oversized stage log: " + stage)
        files[path.name] = {"sha256": sha256(path.read_bytes()), "bytes": path.stat().st_size}
    raw = run_path.read_bytes()
    return assemble_packet(run, sha256(raw), files)


def assemble_packet(run: dict, run_json_sha256: str, files: dict) -> dict:
    """Assemble expected packet from a captured snapshot; performs no I/O."""
    validate_run(run)
    if not HEX.fullmatch(run_json_sha256) or set(files) != {n + ".log" for n in STAGES}:
        raise ValueError("invalid captured artifact set")
    for item in files.values():
        if (not isinstance(item, dict) or not HEX.fullmatch(item.get("sha256", ""))
                or type(item.get("bytes")) is not int or not 0 <= item["bytes"] <= MAX_LOG):
            raise ValueError("invalid captured artifact metadata")
    packet = {
        "schema_version": 1,
        "kind": "klone-evidence-packet",
        "commit": run["before"]["commit"],
        "observed_at": run["completed_at"],
        "overall": run["overall"],
        "stages": {name: run["stages"][name]["status"] for name in STAGES},
        "run_json_sha256": run_json_sha256,
        "files": files,
        "device_identity_verified": False,
        "deployment_approval": False,
        "origin_authentication": "not_provided",
    }
    return {**packet, "packet_sha256": sha256(canonical(packet))}


def verify_packet(directory: Path, packet: dict, anchor: str | None = None) -> dict:
    errors = []
    if not isinstance(packet, dict):
        return {"valid": False, "errors": ["invalid_packet"], "externally_anchored": False}
    expected = build_packet(directory)
    if packet != expected:
        errors.append("packet_or_source_mismatch")
    if anchor is not None and (not HEX.fullmatch(anchor) or anchor != expected["packet_sha256"]):
        errors.append("anchor_mismatch")
    return {"valid": not errors, "errors": errors,
            "packet_sha256": expected["packet_sha256"],
            "externally_anchored": anchor is not None and not errors,
            "origin_authenticated": False, "deployment_approval": False}


def compare_packets(baseline: dict, candidate: dict) -> dict:
    for packet in (baseline, candidate):
        if packet.get("kind") != "klone-evidence-packet":
            raise ValueError("invalid packet kind")
        if not SHA.fullmatch(packet.get("commit", "")):
            raise ValueError("invalid commit")
        if not HEX.fullmatch(packet.get("packet_sha256", "")):
            raise ValueError("invalid packet digest")
        digest = packet["packet_sha256"]
        if sha256(canonical({k: v for k, v in packet.items() if k != "packet_sha256"})) != digest:
            raise ValueError("packet digest mismatch")
        if set(packet.get("stages", {})) != set(STAGES):
            raise ValueError("stage mismatch")
    regressions = [n for n in REQUIRED
                   if baseline["stages"][n] == "passed" and candidate["stages"][n] != "passed"]
    improvements = [n for n in REQUIRED
                    if baseline["stages"][n] != "passed" and candidate["stages"][n] == "passed"]
    changed_logs = [n for n in STAGES
                    if baseline["files"][n + ".log"]["sha256"] !=
                    candidate["files"][n + ".log"]["sha256"]]
    return {
        "baseline": baseline["commit"], "candidate": candidate["commit"],
        "regressed_stages": regressions, "improved_stages": improvements,
        "changed_logs": changed_logs,
        "manual_review_required": True, "deployment_approval": False,
        "note": "Log changes indicate different output, not necessarily regression causality",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("pack")
    make.add_argument("--run-directory", required=True, type=Path)
    make.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--run-directory", required=True, type=Path)
    verify.add_argument("--packet", required=True, type=Path)
    verify.add_argument("--anchor", help="independently stored packet SHA-256")
    diff = commands.add_parser("compare")
    diff.add_argument("--baseline", required=True, type=Path)
    diff.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            result = build_packet(args.run_directory)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        elif args.command == "verify":
            result = verify_packet(args.run_directory, _read_json(args.packet), args.anchor)
        else:
            result = compare_packets(_read_json(args.baseline), _read_json(args.candidate))
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 2 if args.command == "verify" and not result["valid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
