"""KLONE evidence triage: deterministic, non-authoritative test failure hints.

Never modifies source files, starts servers, approves deployments or calls an LLM.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path

from klone.evidence_network import _read_json, compare_packets, SHA


HINTS = {
    "syntax": ("Python syntax/import", "src/klone", "Run compileall and inspect the first SyntaxError"),
    "cognition": ("Cognition model", "src/klone", "Run test_cognition*.py and compare deterministic seeds"),
    "full": ("Full regression suite", "tests", "Inspect failing pytest node IDs and first traceback"),
    "local_deploy": ("Local deployment", "tests/test_local_deploy.py",
                     "Check port validation, process isolation and Termux-specific behavior"),
    "torch_probe": ("Optional Torch capability", "scripts", "Check optional dependency availability only"),
}


def triage(baseline: dict, candidate: dict) -> dict:
    comparison = compare_packets(baseline, candidate)
    hints = []
    for name in comparison["regressed_stages"]:
        area, location, next_step = HINTS[name]
        hints.append({"stage": name, "area": area, "location_hint": location,
                      "next_step": next_step, "confidence": "heuristic_only"})
    optional_before = baseline["stages"]["torch_probe"]
    optional_after = candidate["stages"]["torch_probe"]
    if optional_before != optional_after:
        area, location, next_step = HINTS["torch_probe"]
        hints.append({"stage": "torch_probe", "area": area,
                      "location_hint": location, "next_step": next_step,
                      "confidence": "optional_capability_only"})
    verdict = "review_regression" if comparison["regressed_stages"] else (
        "review_changed_logs" if comparison["changed_logs"] else "no_stage_regression_detected")
    return {"schema_version": 1, "baseline": comparison["baseline"],
            "candidate": comparison["candidate"], "verdict": verdict,
            "comparison": comparison, "hints": hints,
            "causality_established": False, "patch_authorized": False,
            "deployment_approval": False, "manual_review_required": True}


def html_report(result: dict) -> str:
    rows = "".join(
        "<tr><td>" + escape(item["stage"]) + "</td><td>" +
        escape(item["area"]) + "</td><td>" + escape(item["location_hint"]) +
        "</td><td>" + escape(item["next_step"]) + "</td></tr>"
        for item in result["hints"]
    )
    return (
        "<!doctype html><html lang='fi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>KLONE regressiotutkinta</title><style>"
        "body{font:16px system-ui;background:#111827;color:#f9fafb;"
        "max-width:1000px;margin:2rem auto;padding:1rem}"
        "table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}"
        "td,th{padding:.7rem;border-bottom:1px solid #475569;text-align:left}"
        "</style></head><body><h1>KLONE · Regressiotutkinta</h1>"
        "<p>Lähtöversio: <code>" + escape(result["baseline"]) +
        "</code></p><p>Uusi versio: <code>" + escape(result["candidate"]) +
        "</code></p><p>Tila: " + escape(result["verdict"]) + "</p>"
        "<p>Vihjeet ovat heuristiikkaa, eivät osoitus syy-yhteydestä."
        " Korjauksia tai julkaisuja ei hyväksytä automaattisesti.</p>"
        "<table><thead><tr><th>Testi</th><th>Alue</th><th>Mahdollinen sijainti</th>"
        "<th>Seuraava tutkimus</th></tr></thead><tbody>" + rows +
        "</tbody></table></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--html-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = triage(_read_json(args.baseline), _read_json(args.candidate))
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    for path, contents in (
        (args.json_output, json.dumps(result, indent=2, sort_keys=True) + "\n"),
        (args.html_output, html_report(result)),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "hints": len(result["hints"]),
                      "html": str(args.html_output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
