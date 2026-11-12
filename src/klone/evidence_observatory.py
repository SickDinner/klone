"""Generate a static, offline evidence history dashboard from local test runs."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from klone.evidence_status import inspect
from klone.evidence_network import REQUIRED


def collect(root: Path) -> list[dict]:
    if not root.is_dir():
        raise ValueError("run root not found")
    runs = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.is_symlink():
            continue
        packet = directory / "evidence-packet.json"
        if not packet.is_file():
            candidates = sorted(directory.glob("*packet*.json"))
            if candidates:
                packet = candidates[0]
        status = inspect(directory, packet)
        status["run_name"] = directory.name
        runs.append(status)
    return runs




def compare_history(runs: list[dict]) -> list[dict]:
    """Compare consecutive run statuses; names are ordering hints, not proof of time."""
    changes = []
    for previous, current in zip(runs, runs[1:]):
        before = previous["stage_statuses"]
        after = current["stage_statuses"]
        regressions = [name for name in REQUIRED
                       if before.get(name) == "passed" and after.get(name) != "passed"]
        recoveries = [name for name in REQUIRED
                      if before.get(name) != "passed" and after.get(name) == "passed"]
        changes.append({
            "from_run": previous["run_name"], "to_run": current["run_name"],
            "from_commit": previous["commit"], "to_commit": current["commit"],
            "regressed_stages": regressions, "recovered_stages": recoveries,
            "integrity_changed": previous["integrity_ok"] != current["integrity_ok"],
            "comparable": previous["integrity_ok"] and current["integrity_ok"],
            "manual_review_required": True,
            "note": "Directory order is not causal or chronological proof.",
        })
    return changes

def render(runs: list[dict]) -> str:
    rows = []
    for run in runs:
        cells = [
            run["run_name"], run["commit"] or "unknown",
            "yes" if run["integrity_ok"] else "NO",
            "yes" if run["required_stages_passed"] else "NO",
            ", ".join(k + ": " + v for k, v in run["stage_statuses"].items()),
            ", ".join(run["errors"]) or "none",
            run["decision"],
        ]
        rows.append("<tr>" + "".join("<td>" + html.escape(str(value)) +
                    "</td>" for value in cells) + "</tr>")
    headings = ["Run", "Commit", "Integrity", "Required tests", "Stages",
                "Errors", "Decision"]
    diff_rows = []
    for change in compare_history(runs):
        values = [change["from_run"], change["to_run"],
                  ", ".join(change["regressed_stages"]) or "none",
                  ", ".join(change["recovered_stages"]) or "none",
                  "yes" if change["comparable"] else "NO"]
        diff_rows.append("<tr>" + "".join("<td>" + html.escape(str(value)) +
                         "</td>" for value in values) + "</tr>")
    return ("""<!doctype html><html lang="fi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KLONE Evidence Observatory</title>
<style>body{font:15px system-ui;background:#111827;color:#e5e7eb;margin:2rem}
table{border-collapse:collapse;width:100%}td,th{padding:.7rem;border-bottom:1px solid #374151;
text-align:left;vertical-align:top}th{color:#93c5fd}td{overflow-wrap:anywhere}
small{color:#9ca3af}</style></head><body><h1>KLONE Evidence Observatory</h1>
<p>Offline, read-only test history. All origins unverified; no deployment approvals.</p>
<table><thead><tr>""" +
            "".join("<th>" + html.escape(x) + "</th>" for x in headings) +
            "</tr></thead><tbody>" + "".join(rows) +
            "</tbody></table><h2>Adjacent run comparisons</h2><p>Directory ordering is not proof of time or causality.</p>" +
            "<table><thead><tr><th>From</th><th>To</th><th>Regressed</th><th>Recovered</th><th>Comparable</th></tr></thead><tbody>" +
            "".join(diff_rows) + "</tbody></table><p><small>Reports describe local file integrity only.</small></p>"
            "</body></html>")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--html-output", required=True, type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    try:
        runs = collect(args.runs_root)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render(runs), encoding="utf-8")
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps({"runs": runs, "comparisons": compare_history(runs)}, sort_keys=True, indent=2) + "\n",
                                    encoding="utf-8")
    print(json.dumps({"runs": len(runs), "html": str(args.html_output),
                      "blocked": sum(x["decision"] == "blocked" for x in runs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
