"""SQLite approval-time guard for *unverified draft approvals* (lab only).

This adapter deliberately has no publication path. It is installed only on an
isolated SQLite connection by a trusted host and calls back into a trusted,
current evidence provider at approval time. It does not authenticate the
provider, secure a signing key, or attest to scientific independence.

Do NOT install this experimental trigger on a production database: it does not
migrate existing receipts and globally denies activation in that connection.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Callable

from .evidence_receipt import EvidenceError, make_subject, verify


class EvidenceApprovalBridge:
    """Fail-closed receipt check integrated with a SQLite state transition.

    `trusted_provider(proposal_id)` must return *current trusted inputs* for
    make_subject: proposal_id, target_version, draft_text, ids, debate, dossier.
    Never pass a request body or model answer directly as the provider.

    The SQLite function is registered on this exact connection, not elsewhere.
    A SQLite writer who can remove triggers still controls its own database.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        secret: bytes,
        trusted_provider: Callable[[str], dict],
        clock: Callable[[], int],
        attach_existing: bool = False,
    ) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("sqlite_connection_required")
        if connection.isolation_level is not None or connection.in_transaction:
            raise ValueError("autocommit_idle_connection_required")
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError("protected_signing_key_required")
        if not callable(trusted_provider) or not callable(clock):
            raise ValueError("trusted_context_required")
        if type(attach_existing) is not bool:
            raise ValueError("invalid_attach_mode")
        self._provider = trusted_provider
        self._clock = clock
        self._secret = secret
        self.connection = connection
        required = {
            "proposal_id", "room_id", "target_version", "patch_sha256", "state"
        }
        cols = {
            row[1] for row in connection.execute("PRAGMA table_info(approval_proposals)")
        }
        if not required.issubset(cols):
            raise ValueError("approval_schema_missing")

        connection.create_function(
            "klone_receipt_guard_v11", 5, self._verify_callback,
        )
        if attach_existing:
            # A second connection/process must register its own SQL callback,
            # but it must not recreate or silently replace the existing schema.
            expected = {
                "evidence_guard_no_update_v11",
                "evidence_guard_no_delete_v11",
                "evidence_guard_binding_immutable_v11",
                "evidence_guard_approve_v11",
                "evidence_guard_activation_v11",
            }
            existing = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )}
            columns = {row[1] for row in connection.execute(
                "PRAGMA table_info(evidence_guard_receipts_v11)"
            )}
            if not expected.issubset(existing) or not {
                "proposal_id", "receipt_json"
            }.issubset(columns):
                raise ValueError("existing_evidence_bridge_incomplete")
            return

        # Schema changes intentionally separate from approval transactions.
        # The name is scoped to the lab; never run against production SQLite.
        connection.executescript("""
            CREATE TABLE evidence_guard_receipts_v11 (
                proposal_id TEXT PRIMARY KEY,
                receipt_json TEXT NOT NULL CHECK(length(receipt_json) BETWEEN 1 AND 8192)
            );
            CREATE TRIGGER evidence_guard_no_update_v11
            BEFORE UPDATE ON evidence_guard_receipts_v11
            BEGIN
                SELECT RAISE(ABORT, 'evidence_receipt_immutable');
            END;
            CREATE TRIGGER evidence_guard_no_delete_v11
            BEFORE DELETE ON evidence_guard_receipts_v11
            BEGIN
                SELECT RAISE(ABORT, 'evidence_receipt_immutable');
            END;
            -- Proposal subject bindings are immutable from creation through
            -- approval. Edits require creating a new proposal, never mutating
            -- a previously signed subject. The ApprovalJournal changes only
            -- state and approver_id during legitimate transitions.
            CREATE TRIGGER evidence_guard_binding_immutable_v11
            BEFORE UPDATE OF proposal_id,room_id,target_version,patch_sha256
            ON approval_proposals
            WHEN NEW.proposal_id IS NOT OLD.proposal_id
              OR NEW.room_id IS NOT OLD.room_id
              OR NEW.target_version IS NOT OLD.target_version
              OR NEW.patch_sha256 IS NOT OLD.patch_sha256
            BEGIN
                SELECT RAISE(ABORT,'evidence_subject_binding_immutable');
            END;
            CREATE TRIGGER evidence_guard_approve_v11
            BEFORE UPDATE OF state ON approval_proposals
            WHEN NEW.state='approved'
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM evidence_guard_receipts_v11 g
                    WHERE g.proposal_id=NEW.proposal_id
                      AND klone_receipt_guard_v11(
                        g.receipt_json,
                        NEW.proposal_id,
                        NEW.room_id,
                        NEW.target_version,
                        NEW.patch_sha256
                      )=1
                ) THEN RAISE(ABORT,'evidence_receipt_denied') END;
            END;
            CREATE TRIGGER evidence_guard_activation_v11
            BEFORE UPDATE OF state ON approval_proposals
            WHEN NEW.state IN ('activating','active')
            BEGIN
                SELECT RAISE(ABORT,'evidence_draft_activation_forbidden');
            END;
        """)

    def _verify_callback(self, receipt_json, proposal_id, room_id, version, patch_sha256):
        """SQLite callback: return 1 only on completely verified current state."""
        try:
            if type(receipt_json) is not str or len(receipt_json) > 8192:
                return 0
            if type(proposal_id) is not str or type(version) is not str:
                return 0
            inputs = self._provider(proposal_id)
            if type(inputs) is not dict or set(inputs) != {
                "proposal_id", "target_version", "draft_text", "ids", "debate", "dossier"
            }:
                return 0
            expected = make_subject(**inputs)
            # The approval journal's patch_sha256 is the exact draft-text
            # SHA-256 in this prototype; other artifact types need a separate
            # well-specified binding protocol.
            if (expected["proposal_id"] != proposal_id
                    or expected["target_version"] != version
                    or expected["room_id"] != room_id
                    or expected["draft_sha256"] != patch_sha256):
                return 0
            receipt = json.loads(receipt_json)
            now = self._clock()
            if type(now) is not int:
                return 0
            return int(verify(receipt, expected, secret=self._secret, now=now))
        except (EvidenceError, TypeError, ValueError, KeyError, OverflowError):
            return 0

    def insert_signed_receipt(self, proposal_id: str, receipt: dict) -> None:
        """Insert once. Signature is reverified on approval, not trusted here."""
        if type(proposal_id) is not str or not proposal_id:
            raise ValueError("invalid_proposal_id")
        payload = json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False)
        if len(payload) > 8192:
            raise ValueError("receipt_too_large")
        self.connection.execute(
            "INSERT INTO evidence_guard_receipts_v11(proposal_id,receipt_json) VALUES (?,?)",
            (proposal_id, payload),
        )
