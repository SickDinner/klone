"""Council72 v3.0: public memory continuity anomaly -> review-only observation.

Never treats a memory drift report as an authenticated source or a vote.
No tools, execution, model calls, memory writes or API publishing.
"""
from __future__ import annotations

from collections.abc import Sequence

from .memory_continuity_v30 import PublicMemoryEvent, check_memory_continuity


def public_memory_continuity_observation(
    before: Sequence[PublicMemoryEvent], after: Sequence[PublicMemoryEvent],
) -> dict:
    """Recheck original snapshots, then build bounded Council72 metadata only."""
    from .council72 import SIGNALS, catalog

    report = check_memory_continuity(before, after)
    courier = catalog()["rings"][0]["member_ids"][2]
    alarm = report["continuity_status"] == "blocked"
    observation = {
        "id": "mem-cont-" + report["report_sha256"][:40],
        "courier_id": courier,
        "claim_key": "public-memory-continuity",
        "source_group": "klone-public-memory-lab",
        "source_ref": "memory-continuity-sha256:" + report["report_sha256"],
        "stance": "unknown",  # A local consistency scan does not prove truth.
        "classification": "public",
        "summary": (
            "Julkisen muistin metatietojatkuvuus: " +
            ("ristiriitoja, ihmistarkastus vaaditaan" if alarm else
             "paikallisesti johdonmukainen, alkupera varmentamatta") +
            "; tapahtumia " + str(report["current_event_count"]) +
            ", korjattuja " + str(report["current_corrected_count"]) + "."
        ),
        "signals": {**SIGNALS, "risk": 0.95 if alarm else 0.5,
                    "evidence_quality": 0.0, "uncertainty": 1.0},
    }
    return {
        "schema_version": 1,
        "kind": "klone-council72-memory-continuity-observation-v30-lab",
        "continuity_report_sha256": report["report_sha256"],
        "continuity_status": report["continuity_status"],
        "observation": observation,
        "source_origin_authenticated": False,
        "room_access_granted": False,
        "council_vote_cast": False,
        "memory_write_enabled": False,
        "execution_enabled": False,
        "approval_granted": False,
        "manual_review_required": True,
    }
