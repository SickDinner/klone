"""Transactional research claim and audit persistence, with explicit caller authority.

This is a low-level database primitive, NOT an authentication endpoint.
Callers must validate the report, reviewer and Hypervisor grant beforehand.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .research_proposals import ClaimProposal, prepare_claim_proposal


@dataclass(frozen=True)
class CommitReceipt:
    proposal_id: str
    claim_id: str
    revision: int
    audit_digest: str


class AtomicResearchLedger:
    """SQLite claim revision + audit event in one IMMEDIATE transaction."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    def commit_verified(
        self, *, proposal: ClaimProposal, reviewer_id: str,
        decision_reason: str, authorized: bool,
    ) -> CommitReceipt:
        """Persist a previously verified approved proposal or fail closed.

        'authorized' is an assertion from the privileged caller, not proof.
        Never expose this method to untrusted callers or accept HTTP flags.
        """
        if authorized is not True:
            raise PermissionError("Privileged authorization required")
        if not isinstance(proposal, ClaimProposal):
            raise ValueError("Invalid proposal")
        expected = prepare_claim_proposal(
            trace_id=proposal.trace_id, report_version=proposal.report_version,
            claim_id=proposal.claim_id, statement=proposal.statement,
            source_refs=proposal.source_refs, requested_status=proposal.requested_status,
            rationale=proposal.rationale,
        )
        if expected != proposal:
            raise ValueError("Proposal integrity mismatch")
        if (not isinstance(reviewer_id, str) or not reviewer_id.strip()
            or len(reviewer_id) > 128 or not isinstance(decision_reason, str)
            or not decision_reason.strip() or len(decision_reason) > 2000):
            raise ValueError("Reviewer and reason required")
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.database_path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""CREATE TABLE IF NOT EXISTS atomic_claims (
                claim_id TEXT NOT NULL, revision INTEGER NOT NULL,
                proposal_id TEXT NOT NULL UNIQUE,
                trace_id TEXT NOT NULL, report_version INTEGER NOT NULL,
                statement TEXT NOT NULL, source_refs_json TEXT NOT NULL,
                status TEXT NOT NULL, rationale TEXT NOT NULL,
                PRIMARY KEY (claim_id, revision))""")
            db.execute("""CREATE TABLE IF NOT EXISTS atomic_claim_audit (
                proposal_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL, revision INTEGER NOT NULL,
                reviewer_id TEXT NOT NULL, decision_reason TEXT NOT NULL,
                audit_digest TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY (proposal_id) REFERENCES atomic_claims(proposal_id))""")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM atomic_claims WHERE proposal_id=?",
                          (proposal.proposal_id,)).fetchone():
                raise ValueError("Proposal already committed")
            revision = db.execute(
                "SELECT COALESCE(MAX(revision),0)+1 FROM atomic_claims WHERE claim_id=?",
                (proposal.claim_id,)).fetchone()[0]
            payload = [proposal.proposal_id, proposal.claim_id, revision,
                       reviewer_id, decision_reason, timestamp]
            audit_digest = hashlib.sha256(json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            db.execute("""INSERT INTO atomic_claims VALUES (?,?,?,?,?,?,?,?,?)""",
                       (proposal.claim_id, revision, proposal.proposal_id,
                        proposal.trace_id, proposal.report_version, proposal.statement,
                        json.dumps(proposal.source_refs), proposal.requested_status,
                        proposal.rationale))
            db.execute("""INSERT INTO atomic_claim_audit VALUES (?,?,?,?,?,?,?)""",
                       (proposal.proposal_id, proposal.claim_id, revision,
                        reviewer_id, decision_reason, audit_digest, timestamp))
        return CommitReceipt(proposal.proposal_id, proposal.claim_id, revision, audit_digest)

    def verify(self, proposal_id: str) -> bool:
        """Verify that a committed claim has a matching audit record and digest."""
        with closing(sqlite3.connect(self.database_path)) as db:
            row = db.execute("""SELECT c.claim_id,c.revision,c.proposal_id,
                c.trace_id,c.report_version,c.statement,c.source_refs_json,
                c.status,c.rationale,a.reviewer_id,a.decision_reason,
                a.audit_digest,a.created_at FROM atomic_claims c
                JOIN atomic_claim_audit a ON a.proposal_id=c.proposal_id
                WHERE c.proposal_id=?""", (proposal_id,)).fetchone()
        if row is None:
            return False
        expected = prepare_claim_proposal(
            trace_id=row[3], report_version=row[4], claim_id=row[0],
            statement=row[5], source_refs=tuple(json.loads(row[6])),
            requested_status=row[7], rationale=row[8],
        )
        if expected.proposal_id != row[2]:
            raise ValueError("Claim integrity failure")
        payload = [row[2], row[0], row[1], row[9], row[10], row[12]]
        digest = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        if digest != row[11]:
            raise ValueError("Audit integrity failure")
        return True


    def reconcile(self) -> tuple[str, ...]:
        """Read-only full-ledger integrity scan; fail closed on anomalies.

        Detects orphan claims, orphan audit rows, revision gaps, modified
        proposal content and modified audit digests. A local administrator
        who can rewrite the entire SQLite database remains out of scope.
        """
        with closing(sqlite3.connect(self.database_path)) as db:
            claims = db.execute("""SELECT claim_id,revision,proposal_id,trace_id,
                report_version,statement,source_refs_json,status,rationale
                FROM atomic_claims ORDER BY claim_id,revision""").fetchall()
            audits = db.execute("""SELECT proposal_id,claim_id,revision,
                reviewer_id,decision_reason,audit_digest,created_at
                FROM atomic_claim_audit ORDER BY proposal_id""").fetchall()
        problems: list[str] = []
        audit_map = {row[0]: row for row in audits}
        claim_ids = {row[2] for row in claims}
        for row in claims:
            claim_id, revision, proposal_id = row[:3]
            try:
                expected = prepare_claim_proposal(
                    trace_id=row[3], report_version=row[4], claim_id=claim_id,
                    statement=row[5], source_refs=tuple(json.loads(row[6])),
                    requested_status=row[7], rationale=row[8])
                if expected.proposal_id != proposal_id:
                    problems.append(f"claim_digest:{proposal_id}")
            except (ValueError, TypeError, KeyError):
                problems.append(f"claim_invalid:{proposal_id}")
            audit = audit_map.get(proposal_id)
            if audit is None:
                problems.append(f"missing_audit:{proposal_id}")
            else:
                if audit[1:3] != (claim_id, revision):
                    problems.append(f"audit_binding:{proposal_id}")
                payload = [proposal_id, claim_id, revision,
                           audit[3], audit[4], audit[6]]
                digest = hashlib.sha256(json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")).hexdigest()
                if digest != audit[5]:
                    problems.append(f"audit_digest:{proposal_id}")
        for audit in audits:
            if audit[0] not in claim_ids:
                problems.append(f"orphan_audit:{audit[0]}")
        revisions: dict[str, list[int]] = {}
        for claim in claims:
            revisions.setdefault(claim[0], []).append(claim[1])
        for claim_id, numbers in revisions.items():
            if numbers != list(range(1, len(numbers) + 1)):
                problems.append(f"revision_gap:{claim_id}")
        return tuple(sorted(problems))
