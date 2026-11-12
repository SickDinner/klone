import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from klone.evidence_all_in_one import generate


class EvidenceAllInOneTests(unittest.TestCase):
    def test_local_only_generates_three_reports(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "output"
            with patch("klone.evidence_all_in_one.collect", return_value=[]):
                result = generate(Path(root), output)
            self.assertEqual(result["decision"], "local_reports_only")
            self.assertEqual(len(result["files"]), 3)
            self.assertFalse(result["deployment_approval"])
            self.assertTrue((output / "regression-graph.json").exists())

    def test_cross_run_generates_dossier_without_approval(self):
        sha = "a" * 40
        comparison = {"local": {"commit": sha, "integrity_ok": True,
                                "required_stages_passed": True},
                      "github": {"commit": sha, "conclusion": "success"},
                      "comparison": {"consistent_claims": True}}
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "out"
            with patch("klone.evidence_all_in_one.collect", return_value=[]), patch(
                    "klone.evidence_all_in_one.cross_check", return_value=comparison):
                result = generate(Path(root), output, cross_run=Path(root))
            self.assertEqual(result["decision"], "manual_review_required")
            self.assertFalse(result["origin_authenticated"])
            dossier = json.loads((output / "decision-dossier.json").read_text())
            self.assertFalse(dossier["deployment_approval"])

    def test_blocked_cross_check_stays_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("klone.evidence_all_in_one.collect", return_value=[]), patch(
                    "klone.evidence_all_in_one.cross_check",
                    return_value={"local": {}, "github": None, "comparison": None}):
                result = generate(Path(root), Path(root) / "out", cross_run=Path(root))
            self.assertEqual(result["decision"], "blocked")

    def test_reject_symlink_output(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "target"
            target.mkdir()
            link = Path(root) / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(ValueError):
                generate(Path(root), link)


if __name__ == "__main__":
    unittest.main()
