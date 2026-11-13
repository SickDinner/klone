import tempfile
import unittest
from pathlib import Path

from klone.evidence_forensics import analyze, main


class EvidenceForensicsTests(unittest.TestCase):
    def test_empty_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(Path(tmp))
            self.assertEqual(result["runs"], [])
            self.assertFalse(result["deployment_approval"])

    def test_missing_manifest_never_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run-1").mkdir()
            result = analyze(root)
            self.assertEqual(len(result["runs"]), 1)
            item = result["runs"][0]
            self.assertFalse(item["artifacts"]["manifest_valid"])
            self.assertFalse(item["origin_authenticated"])
            self.assertTrue(item["requires_manual_review"])

    def test_symlink_run_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run-1").mkdir()
            (root / "alias").symlink_to(root / "run-1", target_is_directory=True)
            self.assertEqual(len(analyze(root)["runs"]), 1)

    def test_output_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            root.mkdir()
            output = Path(tmp) / "report.json"
            self.assertEqual(main(["--runs-root", str(root), "--output", str(output)]), 0)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
