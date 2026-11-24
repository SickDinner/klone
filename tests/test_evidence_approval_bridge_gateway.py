"""Device integration tests with KLONE's actual AtomicApprovalGateway.

Not runnable in the standalone package without the full KLONE source tree.
"""
import copy
from datetime import datetime, timedelta, timezone
import hmac
import json
import secrets
import sqlite3
import unittest
from hashlib import sha256

from klone.evidence_receipt import digest, make_subject, sign
from klone.evidence_approval_bridge import EvidenceApprovalBridge
from klone.approval_access import ApprovalAccess
from klone.approval_atomic_gateway import AtomicApprovalGateway
from klone.approval_identity import SignedActorAssertion
from klone.approval_journal import ApprovalJournal
from klone.approval_keyring import ApprovalKeyring, VerificationKey
from klone.approval_policy import ApprovalProposal


def hashed(obj):
    return {**obj, "report_sha256": digest(obj)}


class SignedApprovalGatewayTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.conn)
        self.now = datetime.now(timezone.utc)
        self.epoch = int(self.now.timestamp())
        self.receipt_key = secrets.token_bytes(32)
        self.actor_key = secrets.token_bytes(32)
        self.counter = 0
        self.dossier = hashed({
            "cards": [{"candidate_id": "a", "source": "A"},
                      {"candidate_id": "b", "source": "B"}],
            "sources": {
                "A": {"source_event_id": 1, "arxiv_id": "2611.13801v1"},
                "B": {"source_event_id": 2, "arxiv_id": "2611.15598v1"},
            },
        })
        self.debate = hashed({"e11_report_sha256": self.dossier["report_sha256"]})
        self.inputs = dict(
            proposal_id="gateway-v11-test", target_version="lab-v1",
            draft_text="UNVERIFIED draft-only test",
            ids=["a", "b"], debate=self.debate, dossier=self.dossier,
        )
        self.subject = make_subject(**self.inputs)
        self.bridge = EvidenceApprovalBridge(
            self.conn, secret=self.receipt_key,
            trusted_provider=lambda pid: self.inputs if pid == self.inputs["proposal_id"] else None,
            clock=lambda: self.epoch,
        )
        pid = self.inputs["proposal_id"]
        self.access = ApprovalAccess(
            self.journal, expires_at={pid: self.now + timedelta(minutes=10)},
        )
        self.keyring = ApprovalKeyring((VerificationKey(
            "lab", self.actor_key, self.epoch - 60, self.epoch + 600,
        ),))
        self.gateway = AtomicApprovalGateway(self.access, keyring=self.keyring)
        self.gateway.propose(
            ApprovalProposal(pid, "test-supervisor", "public-room", "lab-v1",
                             self.subject["draft_sha256"]),
            key_id="lab", assertion=self.signed("test-supervisor", "supervisor"),
            now=self.now,
        )
        for next_state in ("validated", "awaiting_approval"):
            self.gateway.transition(
                pid, next_state, key_id="lab",
                assertion=self.signed("test-supervisor", "supervisor"),
                now=self.now,
            )

    def tearDown(self):
        self.conn.close()

    def signed(self, actor, role):
        self.counter += 1
        payload = json.dumps({
            "actor_id": actor, "role": role,
            "room_id": "public-room",
            "issued_at": self.epoch - self.counter,
        }, sort_keys=True, separators=(",", ":")).encode()
        return SignedActorAssertion(
            payload, hmac.new(self.actor_key, payload, sha256).hexdigest(),
        )

    def put_receipt(self, *, key=None):
        self.bridge.insert_signed_receipt(
            self.inputs["proposal_id"],
            sign(self.subject, secret=key or self.receipt_key,
                 issued_at=self.epoch - 1, ttl=300),
        )

    def approve(self, signed_actor):
        return self.gateway.transition(
            self.inputs["proposal_id"], "approved",
            key_id="lab", assertion=signed_actor, now=self.now,
            current_target_version="lab-v1",
            current_patch_sha256=self.subject["draft_sha256"],
        )

    def state(self):
        return self.journal.get(self.inputs["proposal_id"]).state

    def replay_count(self):
        return self.conn.execute(
            "SELECT COUNT(*) FROM approval_atomic_replay"
        ).fetchone()[0]

    def test_missing_receipt_rollback_and_reuse(self):
        token = self.signed("test-owner", "owner")
        before = self.replay_count()
        events_before = len(self.journal.events(self.inputs["proposal_id"]))
        with self.assertRaises(PermissionError) as caught:
            self.approve(token)
        self.assertIsInstance(caught.exception.__cause__, sqlite3.IntegrityError)
        self.assertEqual(self.replay_count(), before)
        self.assertEqual(len(self.journal.events(self.inputs["proposal_id"])), events_before)
        self.assertEqual(self.state(), "awaiting_approval")
        self.put_receipt()
        approved = self.approve(token)  # same signed assertion still valid
        self.assertEqual(approved.state, "approved")
        self.assertEqual(approved.approver_id, "test-owner")

    def test_signed_wrong_receipt_key_denied(self):
        self.put_receipt(key=secrets.token_bytes(32))
        with self.assertRaises(PermissionError):
            self.approve(self.signed("test-owner", "owner"))
        self.assertEqual(self.state(), "awaiting_approval")

    def test_changed_draft_denied_at_approval(self):
        self.put_receipt()
        self.inputs = {**self.inputs, "draft_text": "Changed after issuance"}
        with self.assertRaises(PermissionError):
            self.approve(self.signed("test-owner", "owner"))
        self.assertEqual(self.state(), "awaiting_approval")

    def test_changed_dossier_denied_at_approval(self):
        self.put_receipt()
        changed = copy.deepcopy(self.dossier)
        changed["cards"][0]["candidate_id"] = "changed"
        self.inputs = {**self.inputs, "dossier": changed}
        with self.assertRaises(PermissionError):
            self.approve(self.signed("test-owner", "owner"))
        self.assertEqual(self.state(), "awaiting_approval")

    def test_valid_draft_never_activates(self):
        self.put_receipt()
        self.approve(self.signed("test-owner", "owner"))
        with self.assertRaises(PermissionError):
            self.gateway.transition(
                self.inputs["proposal_id"], "activating",
                key_id="lab", assertion=self.signed("test-owner", "owner"),
                now=self.now,
                current_target_version="lab-v1",
                current_patch_sha256=self.subject["draft_sha256"],
            )
        self.assertEqual(self.state(), "approved")

    def test_supervisor_cannot_approve(self):
        self.put_receipt()
        with self.assertRaises(PermissionError):
            self.approve(self.signed("test-supervisor", "supervisor"))
        self.assertEqual(self.state(), "awaiting_approval")


if __name__ == "__main__":
    unittest.main()
