"""Read-only KLONE research preview/inspection CLI.

Run: python -m klone.integrated_research_readonly preview --dossier D.json
 --sources S.json --source-dir ./public_sources
Or: python -m klone.integrated_research_readonly inspect
 --database research.sqlite --dossier-id demo --version 1
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .integrated_research_cli import _read_sources
from .integrated_research_operations import preview_public_research, inspect_public_research


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KLONE read-only research operations")
    modes = parser.add_subparsers(dest="mode", required=True)
    preview = modes.add_parser("preview")
    preview.add_argument("--dossier", type=Path, required=True)
    preview.add_argument("--sources", type=Path, required=True)
    preview.add_argument("--source-dir", type=Path, required=True)
    inspect = modes.add_parser("inspect")
    inspect.add_argument("--database", type=Path, required=True)
    inspect.add_argument("--dossier-id", required=True)
    inspect.add_argument("--version", type=int, required=True)
    args = parser.parse_args(argv)
    if args.mode == "preview":
        manifests, contents = _read_sources(args.source_dir, args.sources)
        result = preview_public_research(
            json_text=args.dossier.read_text(encoding="utf-8"),
            manifests=manifests, source_bytes=contents)
        payload = {
            "mode": "preview", "review": asdict(result.review),
            "verified_source_ids": list(result.report.verified_source_ids),
            "markdown": result.report.markdown,
            "database_modified": False,
        }
    else:
        result = inspect_public_research(
            database_path=args.database, dossier_id=args.dossier_id,
            version=args.version)
        payload = {
            "mode": "inspect", "dossier_id": result.dossier_id,
            "version": result.version, "review": asdict(result.review),
            "markdown": result.markdown, "source_bytes_reverified": False,
        }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
