#!/usr/bin/env python3
"""Audit an offline GitHub pull-request snapshot; never merge or approve PRs.

The input is an untrusted JSON snapshot (e.g. GitHub's REST /pulls?state=open).
This is a dependency/topology report, not CI, Android or release evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

MAX_BYTES = 2_000_000
MAX_PRS = 500
BRANCH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,127}\Z")


def _branch(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("ref")
    if (not isinstance(value, str) or not BRANCH.fullmatch(value)
            or value.endswith(("/", ".")) or ".." in value or "//" in value):
        raise ValueError("invalid branch ref")
    return value


def _records(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        payload = payload.get("pull_requests")
    if not isinstance(payload, list) or len(payload) > MAX_PRS:
        raise ValueError("expected bounded pull_requests array")
    result = []
    numbers, heads = set(), set()
    for item in payload:
        if not isinstance(item, dict) or type(item.get("number")) is not int:
            raise ValueError("invalid PR record or number")
        n = item["number"]
        if n <= 0 or n in numbers:
            raise ValueError("duplicate or invalid PR number")
        numbers.add(n)
        if item.get("state") not in ("open", "closed") or type(item.get("draft")) is not bool:
            raise ValueError("invalid PR state or draft flag")
        base = _branch(item.get("base"))
        head = _branch(item.get("head"))
        if item["state"] != "open":
            continue
        if head in heads:
            raise ValueError("two open PRs share one head branch")
        heads.add(head)
        result.append({"number": n, "head": head, "base": base, "draft": item["draft"]})
    return result


def audit(payload: object, main_branch: str = "main") -> dict:
    """Return deterministic, conservative review order from open PR metadata."""
    main_branch = _branch(main_branch)
    records = _records(payload)
    by_head = {r["head"]: r["number"] for r in records}
    by_number = {r["number"]: r for r in records}
    dependencies = {}
    unresolved = []
    for r in records:
        base = r["base"]
        n = r["number"]
        if base == main_branch:
            dependencies[n] = []
        elif base in by_head:
            dependencies[n] = [by_head[base]]
        else:
            dependencies[n] = []
            unresolved.append(n)
    # Topological order is a review sequence, NEVER permission to merge.
    remaining = {n: set(d) for n, d in dependencies.items() if n not in unresolved}
    sequence = []
    while remaining:
        ready = sorted(n for n, deps in remaining.items() if not deps and n not in sequence)
        if not ready:
            break
        for n in ready:
            remaining.pop(n)
            sequence.append(n)
            for deps in remaining.values():
                deps.discard(n)
    blocked = sorted(remaining)
    items = []
    for n in sorted(by_number):
        record = by_number[n]
        if n in unresolved:
            status = "unknown_base"
        elif n in blocked:
            status = "cycle_or_blocked_by_cycle"
        elif record["draft"]:
            status = "draft_review_only"
        else:
            status = "human_review_required"
        items.append({"number": n, "head": record["head"], "base": record["base"],
                      "depends_on": dependencies[n], "status": status})
    return {"schema_version": 1, "kind": "klone-pr-dependency-audit",
            "source_trust": "unverified_offline_snapshot", "automatic_merge_authority": False,
            "ci_verified": False, "android_verified": False, "deployment_approved": False,
            "open_count": len(records), "direct_main_count": sum(r["base"] == main_branch for r in records),
            "review_order_not_merge_permission": sequence,
            "unresolved_base_prs": sorted(unresolved), "cycle_or_blocked_prs": blocked,
            "pull_requests": items}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KLONE: tarkasta PR-riippuvuudet offline, ei yhdistämistä")
    parser.add_argument("snapshot", type=Path, help="Paikallinen GitHub /pulls-JSON")
    parser.add_argument("--main-branch", default="main")
    parser.add_argument("--text", action="store_true", help="Suomenkielinen tiivistelmä")
    args = parser.parse_args(argv)
    try:
        if args.snapshot.is_symlink() or not args.snapshot.is_file():
            raise ValueError("snapshot must be a regular file, not a symlink")
        if args.snapshot.stat().st_size > MAX_BYTES:
            raise ValueError("snapshot too large")
        report = audit(json.loads(args.snapshot.read_text(encoding="utf-8")), args.main_branch)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"KLONE PR audit refused input: {exc}\n")
    if args.text:
        print(f"Avoimia PR:iä {report['open_count']}; suoraan mainiin {report['direct_main_count']}.")
        print("Tarkastusjärjestys (EI yhdistämislupa):", ", ".join("#"+str(n) for n in report["review_order_not_merge_permission"]) or "ei tiedossa")
        print("Tuntematon pohjahaara:", report["unresolved_base_prs"])
        print("Syklinen/estynyt riippuvuus:", report["cycle_or_blocked_prs"])
        print("CI, Android-hyväksyntä ja käyttöönotto: EI TARKISTETTU.")
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
