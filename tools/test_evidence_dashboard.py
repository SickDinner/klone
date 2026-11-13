"""Generate a static, offline, read-only KLONE test evidence dashboard.

Example:
python tools/test_evidence_dashboard.py --database data/test-evidence.sqlite \
  --baseline <40-char-sha> --candidate <40-char-sha> --output dashboard.html
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klone.test_evidence_dashboard import compare_commits, summarize
from klone.test_evidence_ledger import EvidenceLedger


def render(summary: dict, comparison: dict) -> str:
    def cell(value):
        return "<td>" + escape(str(value)) + "</td>"

    def section(title, rows, columns):
        head = "".join("<th>" + escape(name) + "</th>" for name in columns)
        body = "".join("<tr>" + "".join(cell(row.get(key, "")) for key in columns) + "</tr>"
                       for row in rows)
        return "<section><h2>" + escape(title) + "</h2><table><thead><tr>" + head + (
            "</tr></thead><tbody>" + body + "</tbody></table></section>"
        )

    sources = [{"source": source, **data} for source, data in summary["sources"].items()]
    differences = [
        {"type": kind, **entry}
        for kind in ("regressions", "improvements", "missing_baseline_environments",
                     "missing_candidate_environments", "unknown_contexts")
        for entry in comparison.get(kind, [])
    ]
    style = ("body{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;"
             "padding:0 1rem;background:#101820;color:#f1f5f9}"
             "h1{font-size:1.6rem}section{margin:2rem 0}table{width:100%;border-collapse:collapse}"
             "td,th{border-bottom:1px solid #405060;padding:.65rem;text-align:left}"
             "th{color:#a8c5d9}p{line-height:1.5}.warning{color:#ffcf83}"
             "table{display:block;overflow-x:auto}")
    return (
        "<!doctype html><html lang='fi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>KLONE testihistoria</title><style>" + style + "</style></head><body>"
        "<h1>KLONE · Testihistorian työpöytä</h1>"
        "<p>Vertailu: <code>" + escape(comparison["baseline"]) + "</code> → <code>"
        + escape(comparison["candidate"]) + "</code></p>"
        "<p class='warning'>Tila: " + escape(summary["review_state"])
        + ". Havaintoja ei ole automaattisesti hyväksytty.</p>"
        + section("Testilähteet", sources,
                  ["source", "runs", "success", "failure", "pending", "cancelled"])
        + section("Muutokset ja regressiot", differences,
                  ["type", "source", "environment", "reason"])
        + "<p>Staattinen paikallinen raportti. Ei verkkoyhteyksiä eikä tietokantakirjoituksia.</p>"
        "</body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error("evidence database does not exist")
    ledger = EvidenceLedger(args.database)
    summary = summarize(ledger, args.candidate)
    comparison = compare_commits(ledger, args.baseline, args.candidate)
    args.output.write_text(render(summary, comparison), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "review_state": summary["review_state"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
