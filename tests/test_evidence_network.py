"""Evidence Network packet and comparison contract tests."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from klone.evidence_network import build_packet, compare_packets, verify_packet, STAGES


class EvidenceNetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = {
            "schema_version": 1,
            "before": {"commit": "a" * 40, "dirty": False},
            "after": {"commit": "a" * 40, "dirty": False},
            "started_at": "2026-11-12T18:00:00Z",
            "completed_at": "2026-11-12T18:01:00Z",
            "stages": {n: {"status": "passed", "exit_code": 0} for n in STAGES},
            "required_tests_passed": True, "checkout_consistent": True,
            "overall": "passed", "device_identity_verified": False,
            "deployment_approval": False,
        }
        self.run["stages"]["torch_probe"] = {"status": "not_present", "exit_code": None}
        for name in STAGES:
            (self.root / (name + ".log")).write_text("log " + name)
        self.save()

    def save(self):
        (self.root / "run.json").write_text(json.dumps(self.run))

    def test_repeatable_packet(self):
        self.assertEqual(build_packet(self.root), build_packet(self.root))

    def test_verify_and_anchor(self):
        packet = build_packet(self.root)
        result = verify_packet(self.root, packet, packet["packet_sha256"])
        self.assertTrue(result["valid"])
        self.assertTrue(result["externally_anchored"])
        self.assertFalse(result["origin_authenticated"])

    def test_bad_anchor(self):
        packet = build_packet(self.root)
        result = verify_packet(self.root, packet, "0" * 64)
        self.assertFalse(result["valid"])
        self.assertIn("anchor_mismatch", result["errors"])

    def test_modified_log(self):
        packet = build_packet(self.root)
        (self.root / "full.log").write_text("changed")
        self.assertFalse(verify_packet(self.root, packet)["valid"])

    def test_modified_manifest(self):
        packet = build_packet(self.root)
        self.run["stages"]["full"]["status"] = "failed"
        self.run["stages"]["full"]["exit_code"] = 1
        self.run["required_tests_passed"] = False
        self.run["overall"] = "failed"
        self.save()
        self.assertFalse(verify_packet(self.root, packet)["valid"])

    def test_forged_success_rejected(self):
        self.run["before"]["dirty"] = True
        self.save()
        with self.assertRaises(ValueError):
            build_packet(self.root)

    def test_stage_regression_and_changed_log(self):
        old = build_packet(self.root)
        self.run["before"]["commit"] = "b" * 40
        self.run["after"]["commit"] = "b" * 40
        self.run["stages"]["full"] = {"status": "failed", "exit_code": 1}
        self.run["required_tests_passed"] = False
        self.run["overall"] = "failed"
        self.save()
        (self.root / "full.log").write_text("failed")
        new = build_packet(self.root)
        result = compare_packets(old, new)
        self.assertEqual(result["regressed_stages"], ["full"])
        self.assertEqual(result["changed_logs"], ["full"])
        self.assertFalse(result["deployment_approval"])

    def test_optional_torch_absence_is_not_failure(self):
        packet = build_packet(self.root)
        self.assertEqual(packet["overall"], "passed")
        self.assertEqual(packet["stages"]["torch_probe"], "not_present")

    def test_missing_log_rejected(self):
        (self.root / "syntax.log").unlink()
        with self.assertRaises(ValueError):
            build_packet(self.root)

    def test_tampered_packet_digest_rejected(self):
        packet = build_packet(self.root)
        packet["overall"] = "failed"
        with self.assertRaises(ValueError):
            compare_packets(packet, build_packet(self.root))


if __name__ == "__main__":
    unittest.main()
