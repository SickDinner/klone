"""Read-only evidence trust boundary: check manifest claims without trusting them.

The caller must supply a separately obtained trusted commit and a trusted
digest (for example, from a manually verified GitHub artifact). This module
does not fetch, sign, authenticate, upload or approve anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from klone.evidence_network import SHA, HEX, _read_json, build_packet, canonical


def verify_local_packet(run_directory: Path, packet: dict, trusted_commit: str,
                        trusted_packet_sha256: str) -> dict:
    if not isinstance(trusted_commit, str) or not SHA.fullmatch(trusted_commit):
        raise ValueError("trusted commit must be a lowercase 40-character SHA-1")
    if not isinstance(trusted_packet_sha256, str) or not HEX.fullmatch(trusted_packet_sha256):
        raise ValueError("trusted packet hash must be a lowercase SHA-256")
    actual = build_packet(run_directory)
    errors = []
    if packet != actual:
        errors.append("packet_or_files_modified")
    if actual["commit"] != trusted_commit:
        errors.append("trusted_commit_mismatch")
    if actual["packet_sha256"] != trusted_packet_sha256:
        errors.append("trusted_digest_mismatch")
    return {
        "schema_version": 1, "commit": actual["commit"],
        "packet_sha256": actual["packet_sha256"],
        "valid_against_supplied_anchor": not errors, "errors": errors,
        "origin_authenticated": False, "deployment_approval": False,
        "anchor_origin_verified": False,
        "note": "A trusted anchor must be obtained and authenticated independently.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--trusted-commit", required=True)
    parser.add_argument("--trusted-digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_local_packet(
            args.run_directory, _read_json(args.packet),
            args.trusted_commit, args.trusted_digest)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["valid_against_supplied_anchor"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
