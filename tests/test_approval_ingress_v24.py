"""Isolated receipt-intake and denial-audit lab; no approval production API."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from klone.approval_ingress_v24 import (
    _parse_envelope,
    AdmissionDenied,
    AuditUnavailable,
    ScreenedEnvelope,
    V24AuditLedger,
    screen_draft_envelope,
)
from klone.approval_owner_boundary_v22 import OwnerIsolationUnavailable


_MISSING = object()


class AdmissionV24Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="klone-v24-lab-")
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "private_ingress.sqlite")
        self.secret = secrets.token_bytes(32)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.addCleanup(self.db.close)
        V24AuditLedger.initialize_lab_schema(self.db)
        self.ledger = V24AuditLedger(self.db, secret=self.secret, clock=lambda: 1000)
        self.request_id = "1" * 32
        self.payload = self.body()
        self.allow = frozenset({3002})

    def body(self, **changes):
        obj = dict(domain="klone-ingress-v24-lab", action="submit_for_verification",
                   request_id=self.request_id, draft_sha256="a" * 64)
        obj.update(changes)
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

    def screen(self, payload=_MISSING, *, peer=3002, owner=3001, allow=None):
        with (patch("klone.approval_ingress_v24.kernel_peer_uid", return_value=peer),
              patch("klone.approval_ingress_v24._owner_uid", return_value=owner)):
            return screen_draft_envelope(object(), self.payload if payload is _MISSING else payload,
                                         ledger=self.ledger,
                                         allowed_peer_uids=self.allow if allow is None else allow)

    def records(self):
        return self.db.execute(
            "SELECT peer_uid,decision,reason FROM approval_v24_ingress_audit ORDER BY seq"
        ).fetchall()

    def test_synthetic_distinct_uid_is_screened_not_approved(self):
        res = self.screen()
        self.assertIsInstance(res, ScreenedEnvelope)
        self.assertEqual(res.peer_uid, 3002)
        self.assertTrue(self.ledger.verify_chain())
        self.assertEqual(self.records(), [(3002, "screened", "")])

    def test_same_uid_is_denied_and_audited(self):
        with self.assertRaisesRegex(AdmissionDenied, "same_uid_not_isolated"):
            self.screen(peer=3001)
        self.assertEqual(self.records(), [(3001, "denied", "same_uid_not_isolated")])
        self.assertTrue(self.ledger.verify_chain())

    def test_foreign_unallowlisted_uid_is_denied(self):
        with self.assertRaisesRegex(AdmissionDenied, "peer_not_allowlisted"):
            self.screen(peer=3003)
        self.assertEqual(self.records()[0][2], "peer_not_allowlisted")

    def test_claimed_uid_is_not_authentication(self):
        malicious = json.loads(self.payload)
        malicious["uid"] = 3002
        with self.assertRaisesRegex(AdmissionDenied, "invalid_request_envelope"):
            self.screen(json.dumps(malicious).encode(), peer=3003, allow=frozenset({3003}))
        self.assertEqual(self.records()[0][1], "denied")

    def test_kernel_credential_failure_is_logged_as_denial(self):
        with patch("klone.approval_ingress_v24.kernel_peer_uid",
                   side_effect=OwnerIsolationUnavailable("missing")):
            with self.assertRaisesRegex(AdmissionDenied, "kernel_peer_unavailable"):
                screen_draft_envelope(object(), self.payload, ledger=self.ledger,
                                      allowed_peer_uids=self.allow)
        self.assertEqual(self.records(), [(None, "denied", "kernel_peer_unavailable")])

    def test_bad_payload_variants_audited(self):
        variants = [b"", b"not-json", b"\xff", b"{" + b"x" * 4096, b"[]",
                    b'"hello"', b"true", self.body(action="approve_draft"),
                    self.body(domain="other"), self.body(draft_sha256="Z" * 64),
                    self.body(request_id="f" * 10), self.body(extra="no"),
                    self.body(domain=None),
                    b'{"action":"submit_for_verification","action":"submit_for_verification",'
                    b'"domain":"klone-ingress-v24-lab","request_id":"' + b"1"*32 +
                    b'","draft_sha256":"' + b"a"*64 + b'"}',
                    b'{"domain":NaN,"action":"submit_for_verification"}',
                    None, "text", 13]
        for payload in variants:
            with self.subTest(payload=str(payload)[:50]), self.assertRaisesRegex(
                    AdmissionDenied, "invalid_request_envelope"):
                self.screen(payload)
        self.assertEqual(len(self.records()), len(variants))
        self.assertTrue(all(x[1:] == ("denied", "invalid_request_envelope")
                            for x in self.records()))
        self.assertTrue(self.ledger.verify_chain())

    def test_replay_denied_and_audited(self):
        self.screen()
        with self.assertRaisesRegex(AdmissionDenied, "replayed_request"):
            self.screen()
        self.assertEqual([r[1:] for r in self.records()],
                         [("screened", ""), ("denied", "replayed_request")])
        self.assertEqual(self.db.execute("SELECT count(*) FROM approval_v24_ingress_seen")
                         .fetchone()[0], 1)

    def test_replay_id_reused_with_different_draft_is_denied(self):
        self.screen()
        with self.assertRaisesRegex(AdmissionDenied, "replayed_request"):
            self.screen(self.body(draft_sha256="b" * 64))
        self.assertTrue(self.ledger.verify_chain())

    def test_distinct_id_can_be_screened_after_prior_denial(self):
        with self.assertRaises(AdmissionDenied):
            self.screen(self.body(action="activate"))
        self.screen()
        self.assertEqual(len(self.records()), 2)
        self.assertTrue(self.ledger.verify_chain())

    def test_raw_payload_not_in_denial_ledger(self):
        secret_marker = "PRIVATE_CLIENT_TOKEN_123"
        with self.assertRaises(AdmissionDenied):
            self.screen(self.body(extra=secret_marker))
        out = "\n".join(self.db.iterdump())
        self.assertNotIn(secret_marker, out)
        self.assertTrue(self.ledger.verify_chain())

    def test_audit_mutation_detected_and_denies_future_screening(self):
        self.screen()
        self.db.execute("UPDATE approval_v24_ingress_audit SET decision='denied'")
        self.assertFalse(self.ledger.verify_chain())
        with self.assertRaisesRegex(AuditUnavailable, "audit_write_failed"):
            self.screen(self.body(request_id="2" * 32))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM approval_v24_ingress_seen")
                         .fetchone()[0], 1)

    def test_deleted_head_audit_event_detected(self):
        self.screen()
        self.screen(self.body(request_id="2" * 32))
        self.db.execute("DELETE FROM approval_v24_ingress_audit WHERE seq=1")
        self.assertFalse(self.ledger.verify_chain())

    def test_tail_deletion_requires_external_checkpoint(self):
        self.screen()
        self.screen(self.body(request_id="2" * 32))
        self.db.execute("DELETE FROM approval_v24_ingress_audit WHERE seq=2")
        # A malicious owner can truncate a locally sealed log. Do not claim
        # remote tamper evidence without independently stored signed checkpoint.
        self.assertTrue(self.ledger.verify_chain())

    def test_closed_audit_database_fails_closed(self):
        self.db.close()
        with self.assertRaises(AuditUnavailable):
            self.screen()

    def test_audit_write_trigger_failure_rolls_back_seen_marker(self):
        self.db.execute("""CREATE TRIGGER lab_deny_event BEFORE INSERT ON
            approval_v24_ingress_audit BEGIN SELECT RAISE(ABORT,'forced'); END""")
        with self.assertRaises(AuditUnavailable):
            self.screen()
        self.assertEqual(self.db.execute("SELECT count(*) FROM approval_v24_ingress_seen")
                         .fetchone()[0], 0)

    def test_clock_failure_fails_closed(self):
        self.ledger._clock = lambda: "bad"
        with self.assertRaises(AuditUnavailable):
            self.screen()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM approval_v24_ingress_seen")
                         .fetchone()[0], 0)

    def test_invalid_allowlist_rejected(self):
        for allowed in (frozenset(), frozenset({"3002"}), {3002}, frozenset({True})):
            with self.subTest(allowed=allowed), self.assertRaises(ValueError):
                self.screen(allow=allowed)
        self.assertEqual(self.records(), [])

    def test_invalid_ledger_key_rejected(self):
        with self.assertRaises(ValueError):
            V24AuditLedger(self.db, secret=b"short", clock=lambda: 1000)

    def test_schema_must_exist_without_implicit_migration(self):
        fresh = sqlite3.connect(":memory:", isolation_level=None)
        try:
            with self.assertRaises(AuditUnavailable):
                V24AuditLedger(fresh, secret=self.secret, clock=lambda: 1000)
            self.assertEqual(fresh.execute("SELECT count(*) FROM sqlite_master")
                             .fetchone()[0], 0)
        finally:
            fresh.close()

    def test_no_approval_or_publish_interface(self):
        import klone.approval_ingress_v24 as mod
        for x in ("approve", "approve_draft", "revoke", "activate", "publish", "serve", "listen"):
            self.assertFalse(hasattr(mod, x))

    def test_portable_parser_accepts_expected_only(self):
        self.assertEqual(_parse_envelope(self.payload)["request_id"], self.request_id)
        with self.assertRaises(ValueError):
            _parse_envelope(self.body(action="publish"))

    def test_two_independent_db_connections_concurrent_replay(self):
        self.db.close()
        clients = []
        barrier = threading.Barrier(2)
        errs = []
        lock = threading.Lock()

        def worker():
            conn = sqlite3.connect(self.path, isolation_level=None, timeout=10)
            try:
                ledger = V24AuditLedger(conn, secret=self.secret, clock=lambda: 1000)
                barrier.wait(timeout=5)
                try:
                    result = screen_draft_envelope(object(), self.payload,
                                                   ledger=ledger, allowed_peer_uids=self.allow)
                    state = "screened" if result else "error"
                except AdmissionDenied:
                    state = "denied"
                with lock:
                    clients.append(state)
            except BaseException as exc:
                with lock:
                    errs.append(repr(exc))
            finally:
                conn.close()

        ts = [threading.Thread(target=worker) for _ in range(2)]
        # Keep the synthetic kernel/owner identity patches active for the
        # ENTIRE race. Per-thread mock.patch mutates module globals and races
        # during context exit, so it is not valid for a deterministic test.
        with (patch("klone.approval_ingress_v24.kernel_peer_uid", return_value=3002),
              patch("klone.approval_ingress_v24._owner_uid", return_value=3001)):
            for t in ts: t.start()
            for t in ts: t.join(timeout=12)
        self.assertFalse(any(t.is_alive() for t in ts))
        self.assertEqual(errs, [])
        self.assertCountEqual(clients, ["screened", "denied"])
        with sqlite3.connect(self.path) as check:
            self.assertEqual(check.execute("SELECT count(*) FROM approval_v24_ingress_seen")
                             .fetchone()[0], 1)
            self.assertEqual(check.execute("SELECT count(*) FROM approval_v24_ingress_audit")
                             .fetchone()[0], 2)


@unittest.skipUnless(hasattr(socket, "AF_UNIX") and hasattr(socket, "SO_PEERCRED")
                     and hasattr(os, "geteuid") and hasattr(socket, "socketpair"),
                     "requires Linux/Android Unix peer credentials")
class AdmissionV24RealSocketTests(unittest.TestCase):
    def test_kernel_same_uid_rejected_without_mocking(self):
        db = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(db.close)
        V24AuditLedger.initialize_lab_schema(db)
        ledger = V24AuditLedger(db, secret=b"1" * 32, clock=lambda: 1000)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        data = json.dumps(dict(domain="klone-ingress-v24-lab",
                               action="submit_for_verification",
                               request_id="1" * 32, draft_sha256="a" * 64)).encode()
        with self.assertRaisesRegex(AdmissionDenied, "same_uid_not_isolated"):
            screen_draft_envelope(a, data, ledger=ledger,
                                  allowed_peer_uids=frozenset({os.geteuid()}))
        self.assertEqual(db.execute("SELECT decision FROM approval_v24_ingress_audit")
                         .fetchone()[0], "denied")


if __name__ == "__main__":
    unittest.main()
