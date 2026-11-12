"""Independent evidence quorum assessment, conservative by design.

No cryptographic signature verification is implied. A witness ID is a claimed
label until verified by a separately configured trusted verification service.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_network import SHA, HEX, _read_json


def assess(records: list[dict], candidate: str, required: tuple[str, ...] = (
        "github_actions", "termux_bridge")) -> dict:
    if not SHA.fullmatch(candidate):
        raise ValueError("invalid candidate commit")
    if len(set(required)) != len(required) or not required:
        raise ValueError("invalid required witness list")
    accepted = {}
    issues = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(f"record_{index}:invalid")
            continue
        source = record.get("source")
        if source not in required:
            issues.append(f"record_{index}:unexpected_source")
            continue
        if source in accepted:
            issues.append(f"record_{index}:duplicate_source")
            continue
        if record.get("commit") != candidate:
            issues.append(f"record_{index}:commit_mismatch")
            continue
        digest = record.get("packet_sha256")
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            issues.append(f"record_{index}:invalid_digest")
            continue
        if record.get("status") != "success":
            issues.append(f"record_{index}:not_success")
            continue
                accepted[source] = digest
    missing = sorted(set(required) - set(accepted))
    if missing:
        issues.append("missing_sources:" + ",".join(missing))
    return {
        "schema_version": 1, "candidate": candidate,
        "required_sources": sorted(required), "present_sources": sorted(accepted), "origin_authenticated": False,
        "evidence_digests": accepted, "issues": issues,
        "decision": "manual_review_required" if not issues else "blocked",
        "deployment_approval": False,
        "note": "Source labels are untrusted claims. No cryptographic or independent origin verification is performed.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        data = _read_json(args.records, 1024 * 1024)
        if not isinstance(data.get("records"), list) or len(data["records"]) > 100:
            raise ValueError("records must be a list of at most 100 items")
        result = assess(data["records"], args.candidate)
    except (ValueError, TypeError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["decision"] == "manual_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
