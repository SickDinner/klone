"""Transaction-scoped report version gate for co-located SQLite report history.

Requires report history and claims in the SAME SQLite database. BEGIN
IMMEDIATE in the atomic writer serializes competing SQLite writers. Does
not protect against external files, separate DBs or bypassing writers.
"""
from __future__ import annotations

import json
import sqlite3

from .research_proposals import ClaimProposal
from .research_report import ResearchReport
from .research_memory import ResearchMemory


def require_current_report_in_transaction(
    db: sqlite3.Connection, proposal: ClaimProposal,
) -> None:
    if not isinstance(db, sqlite3.Connection) or not isinstance(proposal, ClaimProposal):
        raise ValueError("Invalid transaction gate input")
    row = db.execute(
        """SELECT trace_id, version, room_id, title, markdown,
                  citations_json, content_sha256
           FROM research_report_versions
           WHERE trace_id=? ORDER BY version DESC LIMIT 1""",
        (proposal.trace_id,),
    ).fetchone()
    if row is None or row[1] != proposal.report_version or row[2] != "public-room":
        raise PermissionError("Report missing, stale or not public")
    try:
        citations = json.loads(row[5])
        if not isinstance(citations, list) or not all(type(c) is str for c in citations):
            raise ValueError("Invalid citation list")
        if not set(proposal.source_refs).issubset(citations):
            raise PermissionError("Proposal sources not in report")
        report = ResearchReport(row[0], row[2], row[3], row[4], tuple(citations))
        if ResearchMemory._digest(report) != row[6]:
            raise ValueError("Report content integrity mismatch")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid stored report") from exc
