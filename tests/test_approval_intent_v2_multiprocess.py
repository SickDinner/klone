"""Independent OS processes + separate SQLite connections using real KLONE gateways.

Lab only. Secrets are deliberately distributed to test workers; this does NOT
provide same-UID isolation, production credentials or authenticated IPC.
"""
import hmac
import json
import subprocess
import sys
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


def _worker(request):
    """One independent Python interpreter; all input comes over stdin."""
    index = request["index"]
    path = request["path"]
    keys = {name: bytes.fromhex(value) for name, value in request["keys"].items()}
    inputs = request["inputs"]
    epoch = request["epoch"]
    db = None
    try:
        db = sqlite3.connect(path, isolation_level=None, timeout=25)
        db.execute("PRAGMA busy_timeout=25000")
        journal = ApprovalJournal(db)
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
        # Ready and start markers are non-secret. IPC does not use sem_open,
        # _multiprocessing, POSIX shared memory or signals from the host.
        Path(request["ready_file"]).write_text("ready", encoding="ascii")
        deadline = time.monotonic() + 35
        while not Path(request["start_file"]).exists():
            if time.monotonic() > deadline:
                return (index, "error", "start_timeout")
            time.sleep(0.02)
        actor = _signed_actor(keys["actor"], epoch, request["actor_age"], "owner", "owner")
        signed = SignedDraftIntent(
            bytes.fromhex(request["intent_payload_hex"]), request["intent_signature"]
        )
        try:
            if request["operation"] == "approve_draft":
                result = service.approve_draft(inputs["proposal_id"], key_id="lab",
                                               actor_assertion=actor, intent=signed)
                return (index, "approved", result.state)
            if request["operation"] == "revoke_draft":
                service.revoke_draft(inputs["proposal_id"], reason=request["reason"],
                                     key_id="lab", actor_assertion=actor, intent=signed)
                return (index, "revoked", "ok")
            return (index, "error", "unknown_lab_operation")
        except (PermissionError, ValueError) as exc:
            return (index, "denied", type(exc).__name__)
        except BaseException as exc:
            return (index, "error", f"{type(exc).__name__}: {exc}")
    except BaseException as exc:
        return (index, "error", f"{type(exc).__name__}: {exc}")
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
        # subprocess + stdin pipes: avoids Android/Termux _multiprocessing
        # and SemLock issues, while launching true independent processes.
        start_flag = Path(self.tmp.name) / f"start-{secrets.token_hex(6)}"
        processes = []
        try:
            for i, (operation, reason) in enumerate(operations):
                intent_payload, intent_signature = self._intent(operation, reason)
                ready_flag = Path(self.tmp.name) / f"ready-{secrets.token_hex(6)}-{i}"
                request = {
                    "index": i, "path": self.path, "epoch": self.epoch,
                    "keys": {k: v.hex() for k, v in self.keys.items()},
                    "inputs": self.inputs, "actor_age": 10 + i,
                    "operation": operation, "reason": reason,
                    "intent_payload_hex": intent_payload.hex(),
                    "intent_signature": intent_signature,
                    "ready_file": str(ready_flag), "start_file": str(start_flag),
                }
                child = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "--worker"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True,
                )
                processes.append((child, ready_flag))
                # Ephemeral test secrets are sent only via this child stdin,
                # not command-line arguments or persistent JSON files.
                child.stdin.write(json.dumps(request))
                child.stdin.close()
                child.stdin = None
            deadline = time.monotonic() + 45
            while not all(marker.exists() for _, marker in processes):
                exits = [(p.pid, p.returncode) for p, _ in processes if p.poll() is not None]
                if exits:
                    raise AssertionError(f"child exited before ready: {exits}")
                if time.monotonic() > deadline:
                    raise AssertionError("workers did not become ready")
                time.sleep(0.03)
            start_flag.touch()
            done = []
            for p, _ in processes:
                stdout, stderr = p.communicate(timeout=45)
                self.assertEqual(p.returncode, 0, (p.pid, stderr, stdout))
                try:
                    done.append(json.loads(stdout.strip()))
                except ValueError:
                    self.fail(f"invalid child result: {p.pid} {stdout!r} {stderr!r}")
            self.assertFalse(any(row[1] == "error" for row in done), done)
            return done
        finally:
            start_flag.touch()
            for p, _ in processes:
                if p.poll() is None:
                    p.kill()
                try:
                    p.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=5)

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
    if len(sys.argv) == 2 and sys.argv[1] == "--worker":
        result = _worker(json.load(sys.stdin))
        print(json.dumps(result))
        sys.exit(0 if result[1] != "error" else 1)
    unittest.main()
