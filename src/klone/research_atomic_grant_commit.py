"""Atomic signed-grant nonce + claim + audit commit in one SQLite transaction.

Trusted-service primitive only: caller authenticates principal, obtains live
policy_version, protects signing key and controls the database path.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .research_signed_grants import SignedResearchGrant, verify_research_grant
from .research_proposals import ClaimProposal, prepare_claim_proposal
from .research_atomic_ledger import CommitReceipt


def commit_claim_with_grant(
    *, database_path: Path, proposal: ClaimProposal,
    grant: SignedResearchGrant, principal: str, policy_version: int,
    now: int, key: bytes, decision_reason: str,
) -> CommitReceipt:
    """All three records commit or roll back together. Replay fails closed."""
    if not isinstance(proposal, ClaimProposal):
        raise ValueError("Invalid proposal")
    expected = prepare_claim_proposal(
        trace_id=proposal.trace_id, report_version=proposal.report_version,
        claim_id=proposal.claim_id, statement=proposal.statement,
        source_refs=proposal.source_refs, requested_status=proposal.requested_status,
        rationale=proposal.rationale)
    if expected != proposal:
        raise ValueError("Proposal integrity mismatch")
    if not isinstance(decision_reason, str) or not decision_reason.strip() or len(decision_reason) > 2000:
        raise ValueError("Decision reason required")
    if not verify_research_grant(
        grant=grant, principal=principal, resource_id=proposal.claim_id,
        report_version=proposal.report_version, policy_version=policy_version,
        now=now, key=key):
        raise PermissionError("Signed grant rejected")
    timestamp = datetime.fromtimestamp(now, timezone.utc).isoformat()
    with closing(sqlite3.connect(database_path, timeout=10)) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS research_grant_nonces (
                nonce TEXT PRIMARY KEY, principal TEXT NOT NULL,
                resource_id TEXT NOT NULL, claimed_at INTEGER NOT NULL)""")
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
            db.execute(
                "INSERT INTO research_grant_nonces VALUES (?,?,?,?)",
                (grant.nonce, principal, proposal.claim_id, now))
            if db.execute("SELECT 1 FROM atomic_claims WHERE proposal_id=?",
                          (proposal.proposal_id,)).fetchone():
                raise ValueError("Proposal already committed")
            revision = db.execute(
                "SELECT COALESCE(MAX(revision),0)+1 FROM atomic_claims WHERE claim_id=?",
                (proposal.claim_id,)).fetchone()[0]
            payload = [proposal.proposal_id, proposal.claim_id, revision,
                       principal, decision_reason, timestamp]
            digest = hashlib.sha256(json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
            db.execute("INSERT INTO atomic_claims VALUES (?,?,?,?,?,?,?,?,?)",
                       (proposal.claim_id, revision, proposal.proposal_id,
                        proposal.trace_id, proposal.report_version, proposal.statement,
                        json.dumps(proposal.source_refs), proposal.requested_status,
                        proposal.rationale))
            db.execute("INSERT INTO atomic_claim_audit VALUES (?,?,?,?,?,?,?)",
                       (proposal.proposal_id, proposal.claim_id, revision,
                        principal, decision_reason, digest, timestamp))
            db.commit()
            return CommitReceipt(proposal.proposal_id, proposal.claim_id, revision, digest)
        except Exception:
            db.rollback()
            raise
