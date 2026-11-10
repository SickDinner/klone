from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .research_workflow import run_local_research


def main(argv: list[str] | None = None) -> int:
    """Developer-only local CLI. Not an authentication or sandbox boundary."""
    parser = argparse.ArgumentParser(
        description="KLONE local research: trusted root, explicit files, SQLite audit"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--file", action="append", required=True, dest="files")
    parser.add_argument("--question", required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--save-report", action="store_true", help="Store versioned public report")
    parser.add_argument("--room", default="public-room")
    # Do not expose an arbitrary --role flag. This local developer entrypoint
    # deliberately only supports public-room and public classification.
    args = parser.parse_args(argv)
    if args.room != "public-room":
        parser.error("Developer CLI supports public-room only")
    try:
        outcome = run_local_research(
            root=args.root, relative_paths=args.files,
            question=args.question, room_id="public-room",
            actor_role="owner", trace_id=args.trace_id,
            classification_level="public", database_path=args.database,
            persist_report=args.save_report,
        )
    except Exception as exc:
        print(f"KLONE research failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(outcome.report.markdown)
    if outcome.report_version is not None:
        print(f"Stored report version: {outcome.report_version}", file=sys.stderr)
    print(f"\nAudit events for trace: {outcome.audit_event_count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
