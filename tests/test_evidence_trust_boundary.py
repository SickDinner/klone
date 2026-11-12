import json
from pathlib import Path
import tempfile
import unittest

from klone.evidence_network import STAGES, build_packet
from klone.evidence_trust_boundary import verify_local_packet


class EvidenceTrustBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.commit = "a" * 40
        run = {
            "schema_version": 1,
            "before": {"commit": self.commit, "dirty": False},
            "after": {"commit": self.commit, "dirty": False},
            "started_at": "2026-11-12T10:00:00Z",
            "completed_at": "2026-11-12T10:01:00Z",
            "stages": {n: {"status": "passed", "exit_code": 0} for n in STAGES},
            "required_tests_passed": True, "checkout_consistent": True,
            "overall": "passed", "device_identity_verified": False,
            "deployment_approval": False,
        }
        run["stages"]["torch_probe"] = {"status": "not_present", "exit_code": None}
        (self.root / "run.json").write_text(json.dumps(run), encoding="utf-8")
        for name in STAGES:
            (self.root / (name + ".log")).write_text(name, encoding="utf-8")

    def test_valid_external_anchor_still_not_identity(self):
        packet = build_packet(self.root)
        result = verify_local_packet(self.root, packet, self.commit, packet["packet_sha256"])
        self.assertTrue(result["valid_against_supplied_anchor"])
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["anchor_origin_verified"])
        self.assertFalse(result["deployment_approval"])

    def test_modified_log_rejected(self):
        packet = build_packet(self.root)
        (self.root / "full.log").write_text("tampered", encoding="utf-8")
        result = verify_local_packet(self.root, packet, self.commit, packet["packet_sha256"])
        self.assertFalse(result["valid_against_supplied_anchor"])

    def test_wrong_trusted_commit_rejected(self):
        packet = build_packet(self.root)
        result = verify_local_packet(self.root, packet, "b" * 40, packet["packet_sha256"])
        self.assertIn("trusted_commit_mismatch", result["errors"])

    def test_wrong_trusted_digest_rejected(self):
        packet = build_packet(self.root)
        result = verify_local_packet(self.root, packet, self.commit, "b" * 64)
        self.assertIn("trusted_digest_mismatch", result["errors"])

    def test_invalid_anchor_rejected(self):
        packet = build_packet(self.root)
        with self.assertRaises(ValueError):
            verify_local_packet(self.root, packet, self.commit, "invalid")


if __name__ == "__main__":
    unittest.main()
