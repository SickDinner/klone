"""Build a read-only, hypothesis-only graph from adjacent evidence runs.

A temporal association is never treated as proof of causality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_observatory import compare_history


def graph(runs: list[dict], changed_files: dict | None = None) -> dict:
    if not isinstance(runs, list):
        raise ValueError("runs must be a list")
    changed_files = changed_files or {}
    if not isinstance(changed_files, dict):
        raise ValueError("changed_files must be a mapping")
    nodes = []
    edges = []
    for i, run in enumerate(runs):
        if not isinstance(run, dict):
            raise ValueError("each run must be an object")
        run_id = "run:" + str(i)
        nodes.append({"id": run_id, "kind": "run",
                      "label": str(run.get("run_name", i)),
                      "commit": run.get("commit")})
    for i, diff in enumerate(compare_history(runs)):
        prior = "run:" + str(i)
        current = "run:" + str(i + 1)
        edges.append({"from": prior, "to": current,
                      "relation": "adjacent_in_directory_order",
                      "causal": False})
        for stage in diff["regressed_stages"]:
            stage_id = "regression:" + str(i + 1) + ":" + stage
            nodes.append({"id": stage_id, "kind": "regression", "label": stage})
            edges.append({"from": current, "to": stage_id,
                          "relation": "reported_regression", "causal": False})
            commit = diff["to_commit"]
            files = changed_files.get(commit, [])
            if not isinstance(files, list):
                continue
            for j, filename in enumerate(files[:100]):
                file_id = "file:" + str(i + 1) + ":" + str(j)
                nodes.append({"id": file_id, "kind": "candidate_file",
                              "label": str(filename)})
                edges.append({"from": file_id, "to": stage_id,
                              "relation": "candidate_for_manual_investigation",
                              "causal": False})
    return {
        "schema_version": 1, "nodes": nodes, "edges": edges,
        "causality_established": False, "origin_authenticated": False,
        "deployment_approval": False,
        "note": "Directory adjacency and changed files are investigation hints, not causal proof.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observatory-json", required=True, type=Path)
    parser.add_argument("--changed-files-json", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.observatory_json.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("observatory JSON too large")
        data = json.loads(args.observatory_json.read_text(encoding="utf-8"))
        files = {}
        if args.changed_files_json:
            if args.changed_files_json.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("changed files JSON too large")
            files = json.loads(args.changed_files_json.read_text(encoding="utf-8"))
        result = graph(data["runs"], files)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"nodes": len(result["nodes"]), "edges": len(result["edges"]),
                      "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
