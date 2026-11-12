"""Bounded, read-only inspection of original test artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from klone.evidence_io import (EvidenceIOError, checked_path, json_object,
                               output_path, read_bounded, write_report)
from klone.evidence_network import STAGES, MAX_LOG, validate_run

MAX_MANIFEST = 65536


def snapshot(directory: Path, *, byte_budget: int | None = None) -> tuple[dict, dict[str, bytes]]:
    directory = checked_path(directory, directory=True)
    artifacts, errors, manifest = {}, [], None
    contents: dict[str, bytes] = {}
    consumed = 0
    for name in ("run.json", *(stage + ".log" for stage in STAGES)):
        limit = MAX_MANIFEST if name == "run.json" else MAX_LOG
        try:
            raw = read_bounded(directory / name, min(limit, max(0, byte_budget - consumed))
                               if byte_budget is not None else limit)
        except EvidenceIOError as exc:
            state = ("budget_exceeded" if exc.code == "oversized" and byte_budget is not None
                     and exc.size is not None and exc.size <= limit else exc.code)
            artifacts[name] = {"state": state}
            if exc.size is not None:
                artifacts[name]["bytes"] = exc.size
            errors.append(name + ":" + ("symlink" if exc.code == "symlink_rejected" else state))
            continue
        contents[name] = raw
        consumed += len(raw)
        artifacts[name] = {"state": "present", "bytes": len(raw),
                           "sha256": hashlib.sha256(raw).hexdigest()}
        if name == "run.json":
            try:
                manifest = json_object(raw)
                if type(manifest.get("schema_version")) is not int:
                    raise ValueError("invalid manifest version")
                validate_run(manifest)
            except (ValueError, KeyError, TypeError, AttributeError, UnicodeError, RecursionError) as exc:
                errors.append("run.json:invalid:" + type(exc).__name__)
                manifest = None
    result = {"schema_version": 1, "run_name": directory.name,
            "artifacts": artifacts, "manifest_valid": manifest is not None,
            "commit": manifest["before"]["commit"] if manifest else None,
            "errors": errors, "original_packet_present": (
                (directory / "evidence-packet.json").is_file() and
                not (directory / "evidence-packet.json").is_symlink()),
            "origin_authenticated": False, "deployment_approval": False,
            "note": "Hashes document current bytes, not historical authenticity."}
    return result, contents


def inspect(directory: Path) -> dict:
    return snapshot(directory)[0]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = checked_path(args.runs_root, directory=True)
        output_path(args.output, root)
        items = [inspect(path) for path in sorted(root.iterdir())
                 if path.is_dir() and not path.is_symlink()]
        result = {"schema_version": 1, "runs": items,
                  "origin_authenticated": False, "deployment_approval": False}
        write_report(args.output, json.dumps(result, sort_keys=True, indent=2) + "\n", root)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"runs": len(items), "valid_manifests": sum(
        x["manifest_valid"] for x in items), "with_errors": sum(
        bool(x["errors"]) for x in items)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
