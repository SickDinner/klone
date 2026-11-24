"""Lab-only integration with KLONE's real journal, keyring and evidence bridge."""
import concurrent.futures
import hmac
import json
import secrets
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from klone.approval_access import ApprovalAccess
from klone.approval_atomic_gateway import AtomicApprovalGateway
from klone.approval_identity import SignedActorAssertion
from klone.approval_journal import ApprovalJournal
from klone.approval_keyring import ApprovalKeyring, VerificationKey
from klone.approval_policy import ApprovalProposal
from klone.approval_intent_v2 import (
    BoundDraftApprovalService, SignedDraftIntent, make_intent_payload,
)
from klone.evidence_receipt import digest, make_subject, sign
from klone.evidence_approval_bridge import EvidenceApprovalBridge


def hashed(obj):
    return {**obj, "report_sha256": digest(obj)}


class ApprovalIntentGatewayTests(unittest.TestCase):
    def setUp(self):
        # A shared in-memory connection makes same-process race tests realistic,
        # not a claim of OS/process isolation or separate user credentials.
        self.db = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self.journal = ApprovalJournal(self.db)
        self.now = datetime.now(timezone.utc)
        self.epoch = int(self.now.timestamp())
        self.actor_secret = secrets.token_bytes(32)
        self.receipt_secret = secrets.token_bytes(32)
        self.intent_secret = secrets.token_bytes(32)
        self.counter = 0
        self.dossier = hashed({
            "cards": [{"candidate_id": "a", "source": "A"}, {"candidate_id": "b", "source": "B"}],
            "sources": {
                "A": {"source_event_id": 1, "arxiv_id": "2611.13801v1"},
                "B": {"source_event_id": 2, "arxiv_id": "2611.15598v1"},
            },
        })
        self.debate = hashed({"e11_report_sha256": self.dossier["report_sha256"]})
        self.inputs = dict(
            proposal_id="intent-test-proposal", target_version="lab-v1",
            draft_text="UNVERIFIED draft only", ids=["a", "b"],
            debate=self.debate, dossier=self.dossier,
        )
        self.subject = make_subject(**self.inputs)
        self.bridge = EvidenceApprovalBridge(
            self.db, secret=self.receipt_secret,
            trusted_provider=lambda pid: self.inputs if pid == self.inputs["proposal_id"] else None,
            clock=lambda: self.epoch,
        )
        self.access = ApprovalAccess(
            self.journal,
            expires_at={self.inputs["proposal_id"]: self.now + timedelta(minutes=5)},
        )
        self.ring = ApprovalKeyring((
            VerificationKey("actor", self.actor_secret, self.epoch - 60, self.epoch + 600),
        ))
        self.gateway = AtomicApprovalGateway(self.access, keyring=self.ring)
        pid = self.inputs["proposal_id"]
        self.gateway.propose(
            ApprovalProposal(pid, "proposer", "public-room", "lab-v1",
                             self.subject["draft_sha256"]),
            key_id="actor", assertion=self.actor("proposer", "supervisor"), now=self.now,
        )
        for state in ("validated", "awaiting_approval"):
            self.gateway.transition(
                pid, state, key_id="actor", assertion=self.actor("proposer", "supervisor"),
                now=self.now,
            )
        self.bridge.insert_signed_receipt(
            pid, sign(self.subject, secret=self.receipt_secret,
                      issued_at=self.epoch - 1, ttl=120),
        )
        self.service = BoundDraftApprovalService(
            gateway=self.gateway, intent_secret=self.intent_secret, clock=lambda: self.now,
        )

    def tearDown(self):
        self.db.close()

    def actor(self, actor_id="owner", role="owner"):
        self.counter += 1
        payload = json.dumps({
            "actor_id": actor_id, "role": role, "room_id": "public-room",
            "issued_at": self.epoch - self.counter,
        }, sort_keys=True, separators=(",", ":")).encode()
        return SignedActorAssertion(payload, hmac.new(self.actor_secret, payload, sha256).hexdigest())

    def intent(self, *, operation="approve_draft", actor_id="owner", reason="",
               proposal_id=None, nonce=None):
        payload = make_intent_payload(
            action=operation, actor_id=actor_id, room_id="public-room",
            proposal_id=proposal_id or self.inputs["proposal_id"],
            target_version="lab-v1", patch_sha256=self.subject["draft_sha256"],
            nonce=nonce or secrets.token_hex(16), issued_at=self.epoch - 1,
            ttl_seconds=120, reason=reason,
        )
        return SignedDraftIntent(payload, hmac.new(self.intent_secret, payload, sha256).hexdigest())

    def approve(self, *, actor=None, intent=None):
        return self.service.approve_draft(
            self.inputs["proposal_id"], key_id="actor",
            actor_assertion=actor or self.actor(), intent=intent or self.intent(),
        )

    def state(self):
        return self.journal.get(self.inputs["proposal_id"]).state

    def replay_count(self):
        return self.db.execute("SELECT COUNT(*) FROM approval_v2_intent_replay").fetchone()[0]

    def test_valid_approval_has_one_event_and_intent(self):
        before = len(self.journal.events(self.inputs["proposal_id"]))
        approved = self.approve()
        self.assertEqual(approved.state, "approved")
        self.assertEqual(self.replay_count(), 1)
        self.assertEqual(len(self.journal.events(self.inputs["proposal_id"])), before + 1)

    def test_wrong_proposal_denied_and_replay_not_consumed(self):
        token = self.intent(proposal_id="other")
        with self.assertRaises(PermissionError):
            self.approve(intent=token)
        self.assertEqual(self.replay_count(), 0)
        self.assertEqual(self.state(), "awaiting_approval")
        self.approve()

    def test_revoke_intent_cannot_approve(self):
        with self.assertRaises(PermissionError):
            self.approve(intent=self.intent(operation="revoke_draft", reason="withdraw"))
        self.assertEqual(self.state(), "awaiting_approval")

    def test_wrong_actor_denied(self):
        with self.assertRaises(PermissionError):
            self.approve(intent=self.intent(actor_id="other-owner"))
        self.assertEqual(self.state(), "awaiting_approval")

    def test_supervisor_denied(self):
        with self.assertRaises(PermissionError):
            self.approve(actor=self.actor("proposer", "supervisor"),
                         intent=self.intent(actor_id="proposer"))
        self.assertEqual(self.state(), "awaiting_approval")

    def test_second_approval_cannot_repeat(self):
        receipt = self.intent()
        self.approve(intent=receipt)
        with self.assertRaises(PermissionError):
            self.approve(intent=receipt)
        self.assertEqual(self.replay_count(), 1)

    def test_changed_draft_denied_with_rollback(self):
        self.inputs = {**self.inputs, "draft_text": "Changed without receipt"}
        before = len(self.journal.events(self.inputs["proposal_id"]))
        with self.assertRaises(PermissionError):
            self.approve()
        self.assertEqual(self.state(), "awaiting_approval")
        self.assertEqual(self.replay_count(), 0)
        self.assertEqual(len(self.journal.events(self.inputs["proposal_id"])), before)

    def test_revocation_blocks_approval(self):
        self.service.revoke_draft(
            self.inputs["proposal_id"], reason="withdrawn by owner", key_id="actor",
            actor_assertion=self.actor(),
            intent=self.intent(operation="revoke_draft", reason="withdrawn by owner"),
        )
        self.assertTrue(self.journal.is_revoked(self.inputs["proposal_id"]))
        with self.assertRaises(PermissionError):
            self.approve()
        self.assertEqual(self.state(), "awaiting_approval")
        self.assertEqual(self.replay_count(), 1)

    def test_changed_revocation_reason_denied(self):
        with self.assertRaises(PermissionError):
            self.service.revoke_draft(
                self.inputs["proposal_id"], reason="different", key_id="actor",
                actor_assertion=self.actor(),
                intent=self.intent(operation="revoke_draft", reason="original"),
            )
        self.assertFalse(self.journal.is_revoked(self.inputs["proposal_id"]))
        self.assertEqual(self.replay_count(), 0)

    def test_concurrent_approvals_only_one_wins(self):
        # One facade/connection: RLock serializes callers; SQLite transaction
        # keeps audit event, actor assertion and intent replay atomic.
        requests = [(self.actor(), self.intent()) for _ in range(8)]
        def call(req):
            try:
                return ("ok", self.approve(actor=req[0], intent=req[1]).state)
            except (PermissionError, ValueError) as err:
                return ("denied", type(err).__name__)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(call, requests))
        self.assertEqual(sum(r[0] == "ok" for r in results), 1)
        self.assertEqual(self.state(), "approved")
        self.assertEqual(self.replay_count(), 1)
        self.assertEqual(sum(e.next_state == "approved" for e in self.journal.events(self.inputs["proposal_id"])), 1)

    def test_uninstalled_bridge_denies_service_construction(self):
        other = sqlite3.connect(":memory:", isolation_level=None)
        try:
            journal = ApprovalJournal(other)
            access = ApprovalAccess(journal)
            gateway = AtomicApprovalGateway(access, keyring=self.ring)
            with self.assertRaises(ValueError):
                BoundDraftApprovalService(gateway=gateway, intent_secret=self.intent_secret,
                                          clock=lambda: self.now)
        finally:
            other.close()

    def test_no_activation_publication_methods(self):
        self.assertFalse(hasattr(self.service, "activate"))
        self.assertFalse(hasattr(self.service, "publish"))


if __name__ == "__main__":
    unittest.main()
