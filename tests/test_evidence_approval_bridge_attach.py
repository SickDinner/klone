"""File-backed SQLite attacher regression tests; no production DB is touched."""
import json
import subprocess
import sys
import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path

from klone.evidence_approval_bridge import EvidenceApprovalBridge
from klone.evidence_receipt import digest, make_subject, sign


def _source_records():
    dossier = {
        "cards": [{"candidate_id": "a", "source": "A"}],
        "sources": {"A": {"source_event_id": 1, "arxiv_id": "2611.13801v1"}},
    }
    dossier["report_sha256"] = digest(dossier)
    debate = {"e11_report_sha256": dossier["report_sha256"]}
    debate["report_sha256"] = digest(debate)
    return dict(proposal_id="lab-p1", target_version="v1",
                draft_text="Unverified local lab draft", ids=["a"],
                dossier=dossier, debate=debate)


def _attached_worker(path, secret, inputs):
    """Independent child process + its own DB connection and SQLite callback."""
    db = None
    try:
        db = sqlite3.connect(path, isolation_level=None, timeout=10)
        bridge = EvidenceApprovalBridge(
            db, secret=secret, attach_existing=True,
            trusted_provider=lambda pid: inputs if pid == inputs["proposal_id"] else None,
            clock=lambda: 1005,
        )
        try:
            db.execute("UPDATE approval_proposals SET patch_sha256=? WHERE proposal_id=?",
                       ("a" * 64, inputs["proposal_id"]))
        except sqlite3.IntegrityError:
            immutable = True
        else:
            immutable = False
        db.execute("UPDATE approval_proposals SET state='approved' "
                   "WHERE proposal_id=? AND state='awaiting_approval'",
                   (inputs["proposal_id"],))
        state = db.execute("SELECT state FROM approval_proposals").fetchone()[0]
        return ("ok", immutable, state)
    except BaseException as exc:
        return ("error", type(exc).__name__, str(exc))
    finally:
        if db is not None:
            db.close()


class EvidenceBridgeAttachTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="klone-bridge-attach-")
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "approval.sqlite3")
        self.secret = secrets.token_bytes(32)
        self.inputs = _source_records()
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.execute("""CREATE TABLE approval_proposals (
          proposal_id TEXT PRIMARY KEY, room_id TEXT, target_version TEXT,
          patch_sha256 TEXT, state TEXT
        )""")

    def _bridge(self, db, attach_existing=False):
        return EvidenceApprovalBridge(
            db, secret=self.secret, attach_existing=attach_existing,
            trusted_provider=lambda pid: self.inputs if pid == self.inputs["proposal_id"] else None,
            clock=lambda: 1005,
        )

    def test_attaching_without_guard_schema_is_denied(self):
        with self.assertRaisesRegex(ValueError, "existing_evidence_bridge_incomplete"):
            self._bridge(self.db, attach_existing=True)
        self.assertNotIn("evidence_guard_receipts_v11", {
            row[0] for row in self.db.execute("SELECT name FROM sqlite_master")
        })

    def test_attached_connection_registers_own_guard(self):
        self._bridge(self.db)
        other = sqlite3.connect(self.path, isolation_level=None)
        try:
            self._bridge(other, attach_existing=True)
            functions = other.execute(
                "SELECT name FROM pragma_function_list WHERE name='klone_receipt_guard_v11'"
            ).fetchall()
            self.assertTrue(functions)
            self.assertEqual(self.db.execute(
                "SELECT count(*) FROM sqlite_master WHERE name='evidence_guard_approve_v11'"
            ).fetchone()[0], 1)
        finally:
            other.close()

    def test_independent_process_enforces_receipt_and_subject_binding(self):
        bridge = self._bridge(self.db)
        subject = make_subject(**self.inputs)
        self.db.execute("INSERT INTO approval_proposals VALUES (?,?,?,?,?)", (
            self.inputs["proposal_id"], "public-room", "v1",
            subject["draft_sha256"], "awaiting_approval"))
        bridge.insert_signed_receipt(self.inputs["proposal_id"], sign(
            subject, secret=self.secret, issued_at=1000, ttl=120,
        ))
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            input=json.dumps({"path": self.path, "secret": self.secret.hex(),
                              "inputs": self.inputs}),
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["ok", True, "approved"])
        self.assertEqual(self.db.execute(
            "SELECT state FROM approval_proposals"
        ).fetchone()[0], "approved")



if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--worker":
        request = json.load(sys.stdin)
        response = _attached_worker(request["path"], bytes.fromhex(request["secret"]),
                                    request["inputs"])
        print(json.dumps(response))
        sys.exit(0 if response[0] == "ok" else 1)
    unittest.main()
