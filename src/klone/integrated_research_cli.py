"""Offline KLONE 4.0 research runner.

Usage:
 python -m klone.integrated_research_cli --database research.sqlite \
   --dossier-id demo --dossier dossier.json --sources sources.json \
   --source-dir ./public_sources --output-dir ./results

sources.json: {"archive:1": {"file": "record.txt", "media_type": "text/plain"}}
Only explicitly listed local files are read. The CLI is a local trusted-user
utility, NOT a network endpoint or authentication boundary.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .integrated_research_core import run_integrated_public_research
from .research_source_manifest import manifest_public_source


def _read_sources(source_dir: Path, index_file: Path):
    index = json.loads(index_file.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or len(index) > 5000:
        raise ValueError("Invalid source index")
    root = source_dir.resolve(strict=True)
    manifests, contents = {}, {}
    for source_id, item in index.items():
        if not isinstance(item, dict) or set(item) != {"file", "media_type"}:
            raise ValueError("Invalid source entry")
        filename, media_type = item["file"], item["media_type"]
        if not isinstance(filename, str) or not filename or not isinstance(media_type, str):
            raise ValueError("Invalid source path or media type")
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe source path")
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("Source escapes public source directory")
        if target.stat().st_size > 2_000_000:
            raise ValueError("Source exceeds 2 MB")
        content = target.read_bytes()
        manifests[source_id] = manifest_public_source(
            source_id=source_id, content=content, media_type=media_type)
        contents[source_id] = content
    return manifests, contents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KLONE 4.0 local verified research")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--dossier-id", required=True)
    parser.add_argument("--dossier", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    manifests, contents = _read_sources(args.source_dir, args.sources)
    result = run_integrated_public_research(
        database_path=args.database, dossier_id=args.dossier_id,
        json_text=args.dossier.read_text(encoding="utf-8"),
        manifests=manifests, source_bytes=contents)
    # Output files are intentionally written only after successful processing.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "research-report.md").write_text(
        result.report.markdown, encoding="utf-8")
    summary = {
        "dossier_id": args.dossier_id,
        "version": result.change.version,
        "review": asdict(result.review),
        "verified_source_ids": list(result.report.verified_source_ids),
        "report_file": "research-report.md",
        "status": "manual_review_required",
    }
    (args.output_dir / "research-result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
