"""Independent OS processes + separate SQLite connections using real KLONE gateways.

Lab only. Secrets are deliberately distributed to test workers; this does NOT
provide same-UID isolation, production credentials or authenticated IPC.
"""
import hmac
import json
import multiprocessing
import queue
import secrets
import sqlite3
import tempfile
from contextlib import closing
import time
import unittest
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from klone.approval_access import ApprovalAccess
from klone.approval_atomic_gateway import AtomicApprovalGateway
from klone.approval_identity import SignedActorAssertion
from klone.approval_intent_v2 import BoundDraftApprovalService, SignedDraftIntent, make_intent_payload
from klone.approval_journal import ApprovalJournal
from klone.approval_keyring import ApprovalKeyring, VerificationKey
from klone.approval_policy import ApprovalProposal
from klone.evidence_approval_bridge import EvidenceApprovalBridge
from klone.evidence_receipt import digest, make_subject, sign


def _signed_actor(key, epoch, age, actor_id, role):
    body = json.dumps({"actor_id": actor_id, "role": role, "room_id": "public-room",
                       "issued_at": epoch - age}, sort_keys=True,
                      separators=(",", ":")).encode()
    return SignedActorAssertion(body, hmac.new(key, body, sha256).hexdigest())


def _worker(index, operation, reason, path, keys, inputs, epoch,
            actor_age, signed_intent, ready, go, results):
    db = None
    try:
        db = sqlite3.connect(path, isolation_level=None, timeout=25)
        db.execute("PRAGMA busy_timeout=25000")
        journal = ApprovalJournal(db)
        # Every connection must register its own SQLite function; the shared
        # file schema must not be recreated by these child processes.
        EvidenceApprovalBridge(
            db, secret=keys["receipt"], attach_existing=True,
            trusted_provider=lambda pid: inputs if pid == inputs["proposal_id"] else None,
            clock=lambda: epoch,
        )
        access = ApprovalAccess(journal)
        ring = ApprovalKeyring((VerificationKey(
            "lab", keys["actor"], epoch - 60, epoch + 600,
        ),))
        gateway = AtomicApprovalGateway(access, keyring=ring)
        service = BoundDraftApprovalService(
            gateway=gateway, intent_secret=keys["intent"],
            clock=lambda: datetime.fromtimestamp(epoch, timezone.utc),
        )
        ready.put((index, "ready"))
        if not go.wait(35):
            results.put((index, "error", "start_timeout"))
            return
        actor = _signed_actor(keys["actor"], epoch, actor_age, "owner", "owner")
        signed = SignedDraftIntent(*signed_intent)
        try:
            if operation == "approve_draft":
                result = service.approve_draft(inputs["proposal_id"], key_id="lab",
                                               actor_assertion=actor, intent=signed)
                results.put((index, "approved", result.state))
            elif operation == "revoke_draft":
                service.revoke_draft(inputs["proposal_id"], reason=reason, key_id="lab",
                                     actor_assertion=actor, intent=signed)
                results.put((index, "revoked", "ok"))
            else:
                results.put((index, "error", "unknown_lab_operation"))
        except (PermissionError, ValueError) as exc:
            results.put((index, "denied", type(exc).__name__))
        except BaseException as exc:
            results.put((index, "error", f"{type(exc).__name__}: {exc}"))
    except BaseException as exc:
        ready.put((index, "failed", f"{type(exc).__name__}: {exc}"))
    finally:
        if db is not None:
            db.close()


class SeparateProcessApprovalTests(unittest.TestCase):
    """Separate Python interpreters, independently opened connections, same DB file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="klone-intent-mp-")
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "approvals.sqlite3")
        self.epoch = int(time.time())
        self.now = datetime.fromtimestamp(self.epoch, timezone.utc)
        self.keys = {k: secrets.token_bytes(32) for k in ("actor", "receipt", "intent")}
        dossier = {
            "cards": [{"candidate_id": "a", "source": "A"}],
            "sources": {"A": {"source_event_id": 1, "arxiv_id": "2611.13801v1"}},
        }
        dossier["report_sha256"] = digest(dossier)
        debate = {"e11_report_sha256": dossier["report_sha256"]}
        debate["report_sha256"] = digest(debate)
        self.inputs = dict(proposal_id="mp-lab-p1", target_version="v1",
                           draft_text="UNVERIFIED draft for multiprocessing lab",
                           ids=["a"], dossier=dossier, debate=debate)
        self.subject = make_subject(**self.inputs)
        db = sqlite3.connect(self.path, isolation_level=None, timeout=25)
        journal = ApprovalJournal(db)
        bridge = EvidenceApprovalBridge(
            db, secret=self.keys["receipt"],
            trusted_provider=lambda pid: self.inputs if pid == self.inputs["proposal_id"] else None,
            clock=lambda: self.epoch,
        )
        access = ApprovalAccess(journal, expires_at={
            self.inputs["proposal_id"]: self.now + timedelta(minutes=10),
        })
        ring = ApprovalKeyring((VerificationKey(
            "lab", self.keys["actor"], self.epoch - 60, self.epoch + 600,
        ),))
        gw = AtomicApprovalGateway(access, keyring=ring)
        gw.propose(ApprovalProposal(self.inputs["proposal_id"], "proposer",
                                    "public-room", "v1", self.subject["draft_sha256"]),
                   key_id="lab", assertion=_signed_actor(self.keys["actor"], self.epoch,
                                                           1, "proposer", "supervisor"),
                   now=self.now)
        for step, age in (("validated", 2), ("awaiting_approval", 3)):
            gw.transition(self.inputs["proposal_id"], step, key_id="lab",
                          assertion=_signed_actor(self.keys["actor"], self.epoch,
                                                  age, "proposer", "supervisor"),
                          now=self.now)
        bridge.insert_signed_receipt(self.inputs["proposal_id"], sign(
            self.subject, secret=self.keys["receipt"], issued_at=self.epoch - 1,
            ttl=120,
        ))
        db.close()

    def _intent(self, operation, reason):
        payload = make_intent_payload(
            action=operation, actor_id="owner", room_id="public-room",
            proposal_id=self.inputs["proposal_id"], target_version="v1",
            patch_sha256=self.subject["draft_sha256"], issued_at=self.epoch - 1,
            ttl_seconds=120, nonce=secrets.token_hex(16), reason=reason,
        )
        return payload, hmac.new(self.keys["intent"], payload, sha256).hexdigest()

    def _run(self, operations):
        ctx = multiprocessing.get_context("spawn")
        ready, results = ctx.Queue(), ctx.Queue()
        go = ctx.Event()
        workers = []
        try:
            for i, (operation, reason) in enumerate(operations):
                p = ctx.Process(target=_worker, args=(
                    i, operation, reason, self.path, self.keys, self.inputs,
                    self.epoch, 10 + i, self._intent(operation, reason),
                    ready, go, results,
                ))
                p.start()
                workers.append(p)
            startup = []
            for _ in workers:
                startup.append(ready.get(timeout=45))
            self.assertEqual(len(startup), len(workers))
            self.assertTrue(all(item[1] == "ready" for item in startup), startup)
            go.set()
            done = [results.get(timeout=45) for _ in workers]
            for p in workers:
                p.join(timeout=10)
            self.assertTrue(all(p.exitcode == 0 for p in workers),
                            [(p.pid, p.exitcode) for p in workers])
            self.assertFalse(any(row[1] == "error" for row in done), done)
            return done
        finally:
            go.set()
            for p in workers:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=5)
            ready.close()
            results.close()

    def _database(self):
        return sqlite3.connect(self.path, isolation_level=None, timeout=10)

    def test_eight_process_approvals_only_one_is_committed(self):
        done = self._run([("approve_draft", "")] * 8)
        self.assertEqual(sum(d[1] == "approved" for d in done), 1, done)
        self.assertEqual(sum(d[1] == "denied" for d in done), 7, done)
        with closing(self._database()) as db:
            self.assertEqual(db.execute("SELECT state FROM approval_proposals").fetchone()[0],
                             "approved")
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM approval_events WHERE next_state='approved'"
            ).fetchone()[0], 1)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM approval_v2_intent_replay"
            ).fetchone()[0], 1)

    def test_revocation_in_one_process_denies_later_approval_in_another(self):
        revoked = self._run([("revoke_draft", "owner withdrew")])
        self.assertEqual(revoked[0][1], "revoked", revoked)
        denied = self._run([("approve_draft", "")])
        self.assertEqual(denied[0][1], "denied", denied)
        with closing(self._database()) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM approval_revocations"
            ).fetchone()[0], 1)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM approval_events WHERE next_state='approved'"
            ).fetchone()[0], 0)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM approval_v2_intent_replay"
            ).fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
