"""SQLite guard boundary tests; run even without KLONE's approval packages."""
import copy
import secrets
import sqlite3
import unittest

from klone.evidence_receipt import digest, make_subject, sign
from klone.evidence_approval_bridge import EvidenceApprovalBridge


def hashed(data):
    return {**data, "report_sha256": digest(data)}


class SQLiteReceiptBridgeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.execute("""CREATE TABLE approval_proposals (
            proposal_id TEXT PRIMARY KEY, room_id TEXT, target_version TEXT,
            patch_sha256 TEXT, state TEXT
        )""")
        self.secret = secrets.token_bytes(32)
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
            proposal_id="p1", target_version="v1",
            draft_text="UNVERIFIED local draft", ids=["a", "b"],
            debate=self.debate, dossier=self.dossier,
        )
        self.clock = 1005
        self.bridge = EvidenceApprovalBridge(
            self.db, secret=self.secret,
            trusted_provider=lambda pid: self.inputs if pid == "p1" else None,
            clock=lambda: self.clock,
        )
        self.subject = make_subject(**self.inputs)
        self.db.execute(
            "INSERT INTO approval_proposals VALUES (?,?,?,?,?)",
            ("p1", "public-room", "v1", self.subject["draft_sha256"], "awaiting_approval"),
        )

    def tearDown(self):
        self.db.close()

    def insert(self, *, key=None):
        receipt = sign(self.subject, secret=key or self.secret, issued_at=1000)
        self.bridge.insert_signed_receipt("p1", receipt)

    def approve(self):
        self.db.execute(
            "UPDATE approval_proposals SET state='approved' WHERE proposal_id='p1'"
        )

    def test_missing_receipt_denied(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()
        self.assertEqual(self.db.execute("SELECT state FROM approval_proposals").fetchone()[0],
                         "awaiting_approval")

    def test_valid_receipt_approved_draft_only(self):
        self.insert()
        self.approve()
        self.assertEqual(self.db.execute("SELECT state FROM approval_proposals").fetchone()[0],
                         "approved")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE approval_proposals SET state='activating'")

    def test_wrong_key_denied(self):
        self.insert(key=secrets.token_bytes(32))
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_changed_text_denied(self):
        self.insert()
        self.inputs = {**self.inputs, "draft_text": "Different draft"}
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_changed_card_set_denied(self):
        self.insert()
        self.inputs = {**self.inputs, "ids": ["a"]}
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_changed_source_denied(self):
        self.insert()
        changed = copy.deepcopy(self.dossier)
        changed["sources"]["B"]["arxiv_id"] = "2611.99999v1"
        self.inputs = {**self.inputs, "dossier": changed}
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_missing_or_changed_target_denied(self):
        self.insert()
        self.db.execute("UPDATE approval_proposals SET target_version='v2'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_patch_hash_changed_denied(self):
        self.insert()
        self.db.execute("UPDATE approval_proposals SET patch_sha256=?", ("a"*64,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_expired_receipt_denied(self):
        self.insert()
        self.clock = 1300
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_receipt_update_and_delete_denied(self):
        self.insert()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE evidence_guard_receipts_v11 SET receipt_json='{}'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM evidence_guard_receipts_v11")

    def test_untrusted_provider_denied(self):
        self.insert()
        self.inputs = {"proposal_id": "p1"}
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()

    def test_bad_room_denied(self):
        self.insert()
        self.db.execute("UPDATE approval_proposals SET room_id='restricted-room'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.approve()


if __name__ == "__main__":
    unittest.main()
