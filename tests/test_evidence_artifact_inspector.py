import tempfile
import unittest
from pathlib import Path

from klone.evidence_artifact_inspector import inspect


class ArtifactInspectorTests(unittest.TestCase):
    def test_missing_files_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect(Path(tmp))
            self.assertFalse(result["manifest_valid"])
            self.assertEqual(result["artifacts"]["run.json"]["state"], "missing")
            self.assertFalse(result["deployment_approval"])

    def test_hashes_original_bytes_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "syntax.log"
            log.write_bytes(b"original")
            before = log.read_bytes()
            result = inspect(root)
            self.assertEqual(result["artifacts"]["syntax.log"]["bytes"], 8)
            self.assertEqual(log.read_bytes(), before)

    def test_nested_null_stage_is_reported_not_raised(self):
        import json
        from klone.evidence_network import STAGES
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {"schema_version": 1, "before": {"commit": "a" * 40},
                        "after": {"commit": "a" * 40},
                        "stages": {name: {"status": "passed", "exit_code": 0}
                                   for name in STAGES}}
            manifest["stages"]["full"] = None
            (root / "run.json").write_text(json.dumps(manifest))
            result = inspect(root)
            self.assertFalse(result["manifest_valid"])
            self.assertTrue(any(e.startswith("run.json:invalid:") for e in result["errors"]))

    def test_reject_directory_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alias = root / "alias"
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                inspect(alias)

    def test_reject_artifact_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "syntax.log").symlink_to(root / "elsewhere")
            result = inspect(root)
            self.assertEqual(result["artifacts"]["syntax.log"]["state"],
                             "symlink_rejected")


if __name__ == "__main__":
    unittest.main()
