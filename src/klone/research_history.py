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
    rows = []
    for row in report["entries"]:
        observation = row["observation"]
        values = [row["label"], row["commit"]]
        if observation is None:
            values += ["Not recorded"] + ["Not recorded"] * 5
        else:
            counts = observation["counts"]
            values += [observation["status"], counts["passed"],
                       counts["failed"], counts["errors"], counts["skipped"],
                       observation["duration_seconds"]]
        rows.append("<tr>" + "".join(cell(x) for x in values) + "</tr>")
    limitations = "".join("<li>" + escape(x) + "</li>" for x in report["limitations"])
    headings = ("Label", "Claimed commit", "Status", "Passed", "Failed",
                "Errors", "Skipped", "Duration (s)")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>KLONE research history</title><style>"
        "body{font:16px system-ui,sans-serif;margin:2rem auto;max-width:75rem;padding:0 1rem}"
        ".table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}"
        "th,td{text-align:left;padding:.6rem;border-bottom:1px solid #888;"
        "overflow-wrap:anywhere}td:nth-child(2){max-width:20rem}"
        "</style></head><body><main><h1>KLONE research history</h1>"
        "<ul>" + limitations + "</ul><div class='table-wrap'>"
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
