import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("termux_evidence_pipeline", TOOLS / "termux_evidence_pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class TermuxEvidencePipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.commit = "a" * 40
        self.report = {
            "schema_version": 1,
            "before": {"commit": self.commit, "dirty": False},
            "after": {"commit": self.commit, "dirty": False},
            "stages": {name: {"status": "passed", "exit_code": 0}
                       for name in pipeline.REQUIRED},
            "required_tests_passed": True,
            "checkout_consistent": True,
            "overall": "passed",
            "started_at": "2026-11-12T18:00:00+00:00",
            "completed_at": "2026-11-12T18:01:00+00:00",
            "device_identity_verified": False,
            "deployment_approval": False,
        }
        self.report["stages"]["torch_probe"] = {"status": "not_present", "exit_code": None}
        for name in pipeline.REQUIRED:
            (self.directory / (name + ".log")).write_text("ok")
        self.save()

    def save(self):
        (self.directory / "run.json").write_text(json.dumps(self.report))

    def test_success_and_idempotent_import(self):
        db = self.directory / "evidence.sqlite"
        first, inserted, fingerprint = pipeline.import_report(self.directory, db)
        second, inserted_again, fingerprint_again = pipeline.import_report(self.directory, db)
        self.assertEqual(first["status"], "success")
        self.assertTrue(inserted)
        self.assertFalse(inserted_again)
        self.assertEqual(fingerprint, fingerprint_again)
        self.assertFalse(first["details"]["device_identity_verified"])

    def test_dirty_checkout_is_failure(self):
        self.report["before"]["dirty"] = True
        self.report["checkout_consistent"] = False
        self.report["overall"] = "failed"
        self.save()
        record, _, _ = pipeline.import_report(self.directory, self.directory / "db.sqlite")
        self.assertEqual(record["status"], "failure")

    def test_rejects_false_success(self):
        self.report["before"]["dirty"] = True
        self.save()
        with self.assertRaises(ValueError):
            pipeline.load_report(self.directory)

    def test_rejects_commit_change(self):
        self.report["after"]["commit"] = "b" * 40
        self.save()
        with self.assertRaises(ValueError):
            pipeline.load_report(self.directory)

    def test_rejects_missing_log(self):
        (self.directory / "full.log").unlink()
        with self.assertRaises(ValueError):
            pipeline.load_report(self.directory)
