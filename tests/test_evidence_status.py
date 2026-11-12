import json
from pathlib import Path
import tempfile
import unittest

from klone.evidence_network import STAGES, build_packet
from klone.evidence_status import inspect


class EvidenceStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet_path = self.root / "packet.json"
        stages = {name: {"status": "passed", "exit_code": 0} for name in STAGES}
        stages["torch_probe"] = {"status": "not_present", "exit_code": None}
        run = {
            "schema_version": 1,
            "before": {"commit": "a" * 40, "dirty": False},
            "after": {"commit": "a" * 40, "dirty": False},
            "started_at": "2026-11-12T10:00:00Z",
            "completed_at": "2026-11-12T10:01:00Z",
            "stages": stages, "required_tests_passed": True,
            "checkout_consistent": True, "overall": "passed",
            "device_identity_verified": False, "deployment_approval": False,
        }
        (self.root / "run.json").write_text(json.dumps(run), encoding="utf-8")
        for name in STAGES:
            (self.root / (name + ".log")).write_text(name, encoding="utf-8")
        self.packet_path.write_text(json.dumps(build_packet(self.root)), encoding="utf-8")

    def test_valid_is_manual_review_only(self):
        result = inspect(self.root, self.packet_path)
        self.assertTrue(result["integrity_ok"])
        self.assertTrue(result["required_stages_passed"])
        self.assertEqual(result["decision"], "manual_review_required")
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["deployment_approval"])

    def test_tampered_log_blocks(self):
        (self.root / "syntax.log").write_text("changed", encoding="utf-8")
        result = inspect(self.root, self.packet_path)
        self.assertFalse(result["integrity_ok"])
        self.assertEqual(result["decision"], "blocked")

    def test_missing_packet_blocks(self):
        self.packet_path.unlink()
        self.assertEqual(inspect(self.root, self.packet_path)["decision"], "blocked")

    def test_missing_log_blocks(self):
        (self.root / "full.log").unlink()
        self.assertEqual(inspect(self.root, self.packet_path)["decision"], "blocked")


if __name__ == "__main__":
    unittest.main()
