"""Bounded, read-only inspection of original test artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from klone.evidence_network import STAGES, MAX_LOG, _read_json, validate_run

MAX_MANIFEST = 65536


def inspect(directory: Path) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("unsafe or missing run directory")
    artifacts = {}
    errors = []
    manifest = None
    for name in ("run.json", *(stage + ".log" for stage in STAGES)):
        path = directory / name
        if path.is_symlink():
            artifacts[name] = {"state": "symlink_rejected"}
            errors.append(name + ":symlink")
            continue
        if not path.is_file():
            artifacts[name] = {"state": "missing"}
            errors.append(name + ":missing")
            continue
        limit = MAX_MANIFEST if name == "run.json" else MAX_LOG
        size = path.stat().st_size
        if size > limit:
            artifacts[name] = {"state": "oversized", "bytes": size}
            errors.append(name + ":oversized")
            continue
        raw = path.read_bytes()
        artifacts[name] = {"state": "present", "bytes": len(raw),
                           "sha256": hashlib.sha256(raw).hexdigest()}
        if name == "run.json":
            try:
                manifest = _read_json(path, MAX_MANIFEST)
                validate_run(manifest)
            except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
                errors.append("run.json:invalid:" + type(exc).__name__)
                manifest = None
    return {"schema_version": 1, "run_name": directory.name,
            "artifacts": artifacts, "manifest_valid": manifest is not None,
            "commit": manifest["before"]["commit"] if manifest else None,
            "errors": errors, "original_packet_present": (
                (directory / "evidence-packet.json").is_file() and
                not (directory / "evidence-packet.json").is_symlink()),
            "origin_authenticated": False, "deployment_approval": False,
            "note": "Hashes document current bytes, not historical authenticity."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.runs_root.resolve(strict=True)
        items = [inspect(path) for path in sorted(root.iterdir())
                 if path.is_dir() and not path.is_symlink()]
        if args.output.is_symlink():
            raise ValueError("symlink output rejected")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = {"schema_version": 1, "runs": items,
                  "origin_authenticated": False, "deployment_approval": False}
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"runs": len(items), "valid_manifests": sum(
        x["manifest_valid"] for x in items), "with_errors": sum(
        bool(x["errors"]) for x in items)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
