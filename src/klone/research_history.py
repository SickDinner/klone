"""Render explicit, operator-supplied research history without network access."""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import re

from .research_test_report import parse_summary

MAX_BYTES = 262144
MAX_ENTRIES = 100


def build_history(entries: list) -> dict:
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_ENTRIES:
        raise ValueError("Expected 1 to 100 observations")
    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Expected observation object")
        label = entry.get("label")
        sha = entry.get("commit")
        if not isinstance(label, str) or not label.strip() or len(label) > 80:
            raise ValueError("Invalid observation label")
        if not isinstance(sha, str) or not re.fullmatch("[0-9a-f]{40}", sha):
            raise ValueError("Invalid commit")
        summary = entry.get("summary")
        if summary is None:
            if entry.get("exit_code") is not None:
                raise ValueError("Missing summary cannot have an exit code")
            rows.append({"label": label, "commit": sha, "observation": None})
        else:
            rows.append({"label": label, "commit": sha,
                         "observation": parse_summary(summary, commit=sha,
                                                      exit_code=entry.get("exit_code"))})
    return {
        "schema": "klone.research_history.v1",
        "entries": rows,
        "limitations": [
            "Operator-supplied summaries, not independently verified.",
            "Input order is preserved; no chronology or comparability is verified.",
            "Missing observations are not zero counts.",
            "Test identities, environment and CI status are not independently checked.",
        ],
    }


def render_history_html(report: dict) -> str:
    def cell(value):
        return "<td>" + escape(str(value)) + "</td>"

    def detail(label, value, extra_class=""):
        return ("<div><dt>" + escape(label) + "</dt><dd" + extra_class + ">"
                + escape(str(value)) + "</dd></div>")

    rows = []
    cards = []
    for row in report["entries"]:
        observation = row["observation"]
        missing = "Not recorded"
        values = [row["label"], row["commit"]]
        if observation is None:
            status = missing
            passed = failed = errors = skipped = duration = subtests = warnings = missing
        else:
            counts = observation["counts"]
            status = observation["status"]
            passed, failed, errors, skipped = (counts[k] for k in
                                                ("passed", "failed", "errors", "skipped"))
            duration = observation["duration_seconds"]
            subtests, warnings = counts["subtests_passed"], counts["warnings"]
        values += [status, passed, failed, errors, skipped, duration, subtests, warnings]
        rows.append("<tr>" + "".join(cell(x) for x in values) + "</tr>")
        cards.append(
            "<article class='observation'><h2>" + escape(row["label"]) + "</h2>"
            "<p class='status'>" + escape(status.replace("_", " ")) + "</p>"
            "<dl class='metrics'>"
            + "".join(detail(label, value) for label, value in (
                ("Passed", passed), ("Subtests passed", subtests), ("Failed", failed),
                ("Errors", errors), ("Skipped", skipped), ("Warnings", warnings),
                ("Duration (s)", duration)))
            + "</dl><dl class='commit'>" + detail("Claimed commit", row["commit"])
            + "</dl></article>"
        )
    limitations = "".join("<li>" + escape(x) + "</li>" for x in report["limitations"])
    headings = ("Label", "Claimed commit", "Status", "Passed", "Failed",
                "Errors", "Skipped", "Duration (s)", "Subtests passed", "Warnings")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>KLONE research history</title><style>"
        ":root{color-scheme:light dark}*{box-sizing:border-box}"
        "body{font:16px/1.5 system-ui,sans-serif;margin:1.25rem auto;max-width:85rem;padding:0 1rem}"
        "h1{font-size:clamp(1.5rem,5vw,2.25rem);line-height:1.2}h2{font-size:1.15rem;margin:0}"
        "li+li{margin-top:.35rem}ul{padding-left:1.3rem}"
        ".observations{display:grid;gap:1rem}.observation{min-width:0;padding:1rem;"
        "border:1px solid #888;border-radius:.75rem;overflow-wrap:break-word}"
        ".status{margin:.4rem 0 1rem;font-weight:600}"
        ".metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin:0}"
        ".metrics>div{min-width:0;border-top:1px solid #888;padding-top:.4rem}"
        "dt{font-size:.85rem}dd{margin:0;font-size:1.15rem;font-weight:600;font-variant-numeric:tabular-nums}"
        ".commit{margin:1rem 0 0}.commit dd{font: .85rem/1.5 monospace;overflow-wrap:anywhere}"
        ".table-wrap{display:none;overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:74rem}"
        "th,td{text-align:left;padding:.6rem;border-bottom:1px solid #888}"
        "th,td:nth-child(n+4){white-space:nowrap}td:nth-child(2){font-family:monospace}"
        "@media(min-width:64rem){.observations{display:none}.table-wrap{display:block}}"
        "@media(max-width:20rem){.metrics{grid-template-columns:1fr}}"
        "</style></head><body><main><h1>KLONE research history</h1>"
        "<ul>" + limitations + "</ul>"
        "<section class='observations' aria-label='Supplied observations in input order'>"
        + "".join(cards) + "</section>"
        "<div class='table-wrap'>"
        "<table><caption>Supplied observations in input order</caption><thead><tr>"
        + "".join("<th scope='col'>" + x + "</th>" for x in headings)
        + "</tr></thead><tbody>" + "".join(rows)
        + "</tbody></table></div></main></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--format", choices=("json", "html"), default="html")
    args = parser.parse_args(argv)
    try:
        with args.path.open("rb") as source:
            raw = source.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("History exceeds byte limit")
        report = build_history(json.loads(raw.decode("utf-8")))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(render_history_html(report) if args.format == "html" else
          json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
