"""Offline evidence decision dossier with deterministic, non-mutating next steps."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from klone.evidence_claims_ledger import ledger
from klone.evidence_shadow_review import review


def build(report: dict) -> dict:
    claims = ledger(report)
    shadow = review(report)
    consistent = (claims["decision"] == "manual_review_required"
                  and shadow["decision"] == "manual_review_required")
    actions = [
        {"priority": "P0", "kind": "verify_provenance",
         "command": None,
         "reason": "Origin of local device and GitHub CI export is not authenticated",
         "requires_human_approval": True},
    ]
    if not consistent:
        actions.insert(0, {"priority": "P0", "kind": "investigate_mismatch",
                           "command": None,
                           "reason": "Cross-environment evidence incomplete or inconsistent",
                           "requires_human_approval": True})
    else:
        actions.append({"priority": "P1", "kind": "reproduce_in_clean_worktree",
                        "command": "python -m pytest -q",
                        "reason": "Re-run the same commit in an isolated environment",
                        "requires_human_approval": True})
    return {
        "schema_version": 1, "claims": claims, "shadow_review": shadow,
        "next_actions": actions,
        "decision": "manual_review_required" if consistent else "blocked",
        "origin_authenticated": False, "deployment_approval": False,
    }


def render(dossier: dict) -> str:
    def cell(value):
        return html.escape(str(value), quote=True)
    rows = "".join(
        "<tr><td>" + cell(item["priority"]) + "</td><td>" +
        cell(item["kind"]) + "</td><td>" + cell(item["reason"]) +
        "</td><td>" + cell(item["command"] or "manual") + "</td></tr>"
        for item in dossier["next_actions"]
    )
    return ("""<!doctype html><html lang="fi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KLONE: todisteraportti</title>
<style>body{font:16px system-ui;background:#111827;color:#e5e7eb;margin:2rem}
table{border-collapse:collapse;width:100%}td,th{padding:.7rem;border-bottom:1px solid #374151;text-align:left}
td{overflow-wrap:anywhere}</style></head><body>
<h1>KLONE: todisteraportti</h1><p>Päätös: """ + cell(dossier["decision"]) +
            """</p><p>Alkuperää ei ole varmennettu. Käyttöönottoa ei hyväksytty.</p>
<h2>Turvalliset jatkotoimet</h2><table><tr><th>Prioriteetti</th><th>Tehtävä</th>
<th>Peruste</th><th>Komento</th></tr>""" + rows + "</table></body></html>")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--html-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.report.stat().st_size > 1024 * 1024:
            raise ValueError("report too large")
        report = json.loads(args.report.read_text(encoding="utf-8"))
        dossier = build(report)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    for path, content in (
        (args.json_output, json.dumps(dossier, indent=2, sort_keys=True) + "\n"),
        (args.html_output, render(dossier)),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(json.dumps({"decision": dossier["decision"], "json": str(args.json_output),
                      "html": str(args.html_output)}))
    return 0 if dossier["decision"] == "manual_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
