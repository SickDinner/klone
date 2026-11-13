import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from klone import evidence_io

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

    def test_android_inaccessible_anchor_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_open = evidence_io.os.open

            def blocked_anchor(path, *args, **kwargs):
                if str(path) == root.anchor:
                    raise PermissionError("Android sandbox")
                return original_open(path, *args, **kwargs)

            with patch.object(evidence_io.os, "open", side_effect=blocked_anchor):
                self.assertEqual(evidence_io.read_bounded(
                    self._make_file(root), 100), b"test")
                evidence_io.write_report(root / "report.json", "{}", root / "runs")
            self.assertEqual((root / "report.json").read_text(), "{}")

    @staticmethod
    def _make_file(root):
        path = root / "sample.log"
        path.write_bytes(b"test")
        (root / "runs").mkdir()
        return path

    def test_output_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            root.mkdir()
            output = Path(tmp) / "report.json"
            self.assertEqual(main(["--runs-root", str(root), "--output", str(output)]), 0)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
