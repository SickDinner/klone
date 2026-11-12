"""Generate all local KLONE evidence reports without mutating application state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_observatory import collect, compare_history, render
from klone.evidence_regression_graph import graph
from klone.evidence_decision_dossier import build, render as render_dossier
from klone.evidence_one_command import run as cross_check


def generate(runs_root: Path, output: Path, *, cross_run: Path | None = None,
             packet: Path | None = None, github_fetch=None) -> dict:
    if output.is_symlink():
        raise ValueError("output directory must not be a symlink")
    runs = collect(runs_root)
    history = {"runs": runs, "comparisons": compare_history(runs)}
    results = {
        "observatory.json": json.dumps(history, sort_keys=True, indent=2) + "\n",
        "observatory.html": render(runs),
        "regression-graph.json": json.dumps(graph(runs), sort_keys=True, indent=2) + "\n",
    }
    decision = "local_reports_only"
    if cross_run is not None:
        selected = packet or cross_run / "evidence-packet.json"
        if not selected.is_file() and packet is None:
            candidates = sorted(cross_run.glob("*packet*.json"))
            if candidates:
                selected = candidates[0]
        if github_fetch is None:
            comparison = cross_check(cross_run, selected)
        else:
            comparison = cross_check(cross_run, selected, github_fetch=github_fetch)
        dossier = build(comparison)
        decision = dossier["decision"]
        results["cross-check.json"] = json.dumps(comparison, sort_keys=True, indent=2) + "\n"
        results["decision-dossier.json"] = json.dumps(dossier, sort_keys=True, indent=2) + "\n"
        results["decision-dossier.html"] = render_dossier(dossier)
    output.mkdir(parents=True, exist_ok=True)
    for filename, contents in results.items():
        destination = output / filename
        if destination.is_symlink():
            raise ValueError("refusing symlink destination: " + filename)
        destination.write_text(contents, encoding="utf-8")
    return {"schema_version": 1, "runs": len(runs), "decision": decision,
            "files": sorted(results), "origin_authenticated": False,
            "deployment_approval": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cross-run", type=Path)
    parser.add_argument("--packet", type=Path)
    args = parser.parse_args(argv)
    try:
        result = generate(args.runs_root, args.output, cross_run=args.cross_run,
                          packet=args.packet)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 2 if result["decision"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
