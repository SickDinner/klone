import tempfile
import unittest
from pathlib import Path

from klone.evidence_recovery_planner import plan


def incomplete(name):
    return {"run_name": name, "category": "incomplete"}


class RecoveryPlannerTests(unittest.TestCase):
    def test_missing_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").mkdir()
            result = plan(root, [incomplete("a")])
            self.assertEqual(result["counts"]["original_manifest_missing"], 1)
            self.assertFalse(result["deployment_approval"])

    def test_manifest_present_without_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "b"
            folder.mkdir()
            (folder / "run.json").write_text("{}", encoding="utf-8")
            result = plan(root, [incomplete("b")])
            self.assertEqual(result["counts"]["inspect_source_artifacts"], 1)
            self.assertFalse((folder / "evidence-packet.json").exists())

    def test_no_changes_to_original_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "c"
            folder.mkdir()
            manifest = folder / "run.json"
            manifest.write_bytes(b"original")
            before = manifest.read_bytes()
            plan(root, [incomplete("c")])
            self.assertEqual(manifest.read_bytes(), before)

    def test_reject_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                plan(Path(tmp), [incomplete("../escape")])

    def test_skip_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(plan(Path(tmp), [
                {"run_name": "verified", "category": "verified"}])["runs"], [])


if __name__ == "__main__":
    unittest.main()
