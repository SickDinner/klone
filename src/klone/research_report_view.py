"""Offline, operator-supplied test observations: comparison and static HTML."""
from __future__ import annotations

import argparse
from html import escape
import json

from .research_test_report import parse_summary


def compare_observations(before, after):
    """Count differences only; test identities and environment are not verified."""
    return {
        "before_commit": before["claimed_commit"],
        "after_commit": after["claimed_commit"],
        "count_delta": {
            key: after["counts"][key] - before["counts"][key]
            for key in sorted(before["counts"])
        },
        "before_status": before["status"],
        "after_status": after["status"],
        "comparability_verified": False,
        "independently_verified": False,
        "limitation": "Aggregate counts only; not proof of regression or improvement.",
    }


def render_html(before, after):
    comparison = compare_observations(before, after)
    rows = []
    for key, delta in comparison["count_delta"].items():
        rows.append(
            "<tr><th scope='row'>" + escape(key) + "</th><td>"
            + escape(str(before["counts"][key])) + "</td><td>"
            + escape(str(after["counts"][key])) + "</td><td>"
            + escape(f"{delta:+d}") + "</td></tr>"
        )
    def value(report, key):
        return escape(str(report[key]))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>KLONE research observations</title><style>"
        "body{font:16px system-ui,sans-serif;max-width:55rem;margin:2rem auto;padding:0 1rem;line-height:1.5}"
        "table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:.5rem;border-bottom:1px solid #999}"
        "code{overflow-wrap:anywhere}.note{border-left:3px solid #777;padding-left:1rem}"
        "</style></head><body><main><h1>KLONE research observations</h1>"
        "<p class='note'>Operator-supplied observations; not independently verified. "
        "Test identity and environment comparability are not verified. "
        "Count changes do not establish regression or improvement.</p>"
        "<h2>Before</h2><p>Claimed commit: <code>" + value(before, "claimed_commit")
        + "</code><br>Status: " + value(before, "status")
        + "<br>Duration (s): " + value(before, "duration_seconds") + "</p>"
        "<h2>After</h2><p>Claimed commit: <code>" + value(after, "claimed_commit")
        + "</code><br>Status: " + value(after, "status")
        + "<br>Duration (s): " + value(after, "duration_seconds") + "</p>"
        "<h2>Count changes</h2><table><thead><tr><th>Metric</th><th>Before</th>"
        "<th>After</th><th>Delta</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></main></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("before", "after"):
        parser.add_argument("--" + prefix + "-commit", required=True)
        parser.add_argument("--" + prefix + "-summary", required=True)
        parser.add_argument("--" + prefix + "-exit-code", type=int, required=True)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args(argv)
    try:
        before = parse_summary(args.before_summary, commit=args.before_commit,
                               exit_code=args.before_exit_code)
        after = parse_summary(args.after_summary, commit=args.after_commit,
                              exit_code=args.after_exit_code)
    except ValueError as exc:
        parser.error(str(exc))
    if args.format == "html":
        print(render_html(before, after))
    else:
        print(json.dumps(compare_observations(before, after), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
