"""Two orthogonal, read-only lenses over the existing 72-member council.

Rows are the nine original rings (8 members each); columns are the eight
founder lines (one member per ring). They are *not* independent agents or
independent sources of evidence. The overlay cannot grant any authority.
"""
from __future__ import annotations

from collections import Counter
from math import ceil

from .cognition_neurocortex import digest
from .council72 import AUTHORITY, _replay_equal, catalog, replay_matches


VOTES = ("endorse", "oppose", "defer")


def _summary(member_ids: list[int], votes: dict[int, str]) -> dict:
    counts = Counter(votes[member_id] for member_id in member_ids)
    return {
        "votes": {key: counts.get(key, 0) for key in VOTES},
        "support_ratio": round(
            (counts["endorse"] + 0.5 * counts["defer"]) / len(member_ids), 6
        ),
    }


def _peer_majority(member_ids: list[int], votes: dict[int, str]) -> str:
    """Two-thirds decisive consensus, excluding the intersection member."""
    counts = Counter(votes[member_id] for member_id in member_ids)
    threshold = ceil(2 * len(member_ids) / 3)
    if counts["endorse"] >= threshold:
        return "endorse"
    if counts["oppose"] >= threshold:
        return "oppose"
    return "mixed_or_deferred"


def cross_review(round_report: dict) -> dict:
    """Produce a replay-bound advisory matrix; reject modified input rounds."""
    if not isinstance(round_report, dict) or not replay_matches(round_report):
        raise ValueError("council round does not replay")

    model = catalog()
    rings = model["rings"]
    founders = model["founder_ids"]
    if len(rings) != 9 or len(founders) != 8:
        raise ValueError("unexpected council topology")

    # The founder ballot (including explicit_input) is the vote in ring 9.
    # No ballot is silently replaced by a simulated member opinion.
    votes = {op["member_id"]: op["vote"] for op in round_report["opinions"]}
    ballots = {ballot["member_id"]: ballot for ballot in round_report["founder_ballots"]}
    if set(ballots) != set(founders):
        raise ValueError("founder ballots do not cover all eight founders")
    for founder_id, ballot in ballots.items():
        votes[founder_id] = ballot["vote"]

    ring_views = []
    for ring in rings:
        ids = list(ring["member_ids"])
        ring_views.append({
            "ring_id": ring["id"], "member_ids": ids,
            **_summary(ids, votes),
        })

    line_views = []
    for position, founder_id in enumerate(founders):
        ids = [ring["member_ids"][position] for ring in rings]
        if ids[-1] != founder_id:
            raise ValueError("founder line and final ring do not align")
        line_views.append({
            "line_id": position + 1, "founder_id": founder_id,
            "member_ids": ids,
            "founder_vote_source": ballots[founder_id]["vote_source"],
            **_summary(ids, votes),
        })

    flattened = [member_id for line in line_views for member_id in line["member_ids"]]
    if len(flattened) != 72 or len(set(flattened)) != 72:
        raise ValueError("member duplication or omission in cross-review matrix")

    conflicts = []
    # Exactly 64 specialist intersections. The ninth-row founders are assessed
    # as part of the founder lines, not counted as additional independent votes.
    for ring in rings[:8]:
        ring_ids = ring["member_ids"]
        for position, member_id in enumerate(ring_ids):
            line = line_views[position]
            ring_peers = [candidate for candidate in ring_ids if candidate != member_id]
            line_peers = [candidate for candidate in line["member_ids"] if candidate != member_id]
            ring_majority = _peer_majority(ring_peers, votes)
            line_majority = _peer_majority(line_peers, votes)
            if {ring_majority, line_majority} == {"endorse", "oppose"}:
                conflicts.append({
                    "ring_id": ring["id"], "line_id": line["line_id"],
                    "member_id": member_id,
                    "member_vote": votes[member_id],
                    "ring_peers": ring_majority,
                    "line_peers": line_majority,
                    "review_required": True,
                })

    references = [
        ref for report in round_report["ring_reports"]
        for ref in report["evidence_refs"]
    ]
    source_groups = len(set(references))
    status = "cross_review_required" if conflicts else "no_structural_split_detected"
    result = {
        "schema_version": 1,
        "kind": "klone-council72-cross-review",
        "source_round_sha256": digest(round_report),
        "source_trace_sha256": round_report["trace_sha256"],
        "catalog_sha256": round_report["catalog_sha256"],
        "topology": {"ring_count": 9, "members_per_ring": 8,
                     "founder_line_count": 8, "members_per_line": 9,
                     "unique_members": 72},
        "ring_views": ring_views,
        "founder_line_views": line_views,
        "cross_checks": {"specialist_cells_evaluated": 64,
                         "strict_peer_majority": "at_least_two_thirds",
                         "conflicts": conflicts,
                         "conflict_count": len(conflicts)},
        "evidence": {
            "references_total": len(references),
            "unique_reference_strings": source_groups,
            "authenticated": False,
            "independent_sources_verified": False,
            "warning": "An opaque reference, repeated member or view does not create independent evidence.",
        },
        "advisory": {
            "status": status,
            "base_decision_status": round_report["decision"]["status"],
            "changes_base_decision": False,
            "human_review_required": True,
            "autonomous_release_allowed": False,
            "method": "ring_peer_vs_founder_line_peer_two_thirds_consensus",
        },
        **AUTHORITY,
    }
    result["cross_review_sha256"] = digest(result)
    return result


def cross_review_replays(round_report: dict, overlay: dict) -> bool:
    try:
        return _replay_equal(overlay, cross_review(round_report))
    except (ValueError, KeyError, TypeError, RecursionError):
        return False


def main(argv: list[str] | None = None) -> int:
    """Termux-friendly read-only CLI; stdout JSON, no automatic disk writes."""
    import argparse
    import json
    from pathlib import Path
    from .council72 import demo_proposal, deliberate
    from .evidence_io import json_object, read_bounded, write_new_report

    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--demo", action="store_true")
    choice.add_argument("--input", type=Path, help="JSON council proposal (64 KiB max)")
    parser.add_argument("--output", type=Path, help="new JSON report, never overwrite")
    parser.add_argument("--runs-root", type=Path,
                        default=Path.home() / "klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        proposal = (demo_proposal() if args.demo else
                    json_object(read_bounded(args.input, 65536)))
        overlay = cross_review(deliberate(proposal))
        rendered = json.dumps(overlay, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
        else:
            print(rendered, end="")
    except (ValueError, OSError, UnicodeError, TypeError, RecursionError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
