import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "import_termux_test_run.py"
spec = importlib.util.spec_from_file_location("import_termux_test_run", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ImportTermuxTestRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        (self.directory / "summary.txt").write_text(
            "syntax: exit=0\ncognition: exit=0\nfull: exit=0\n"
            "local_deploy: exit=0\ntorch_probe: exit=2\n",
            encoding="utf-8",
        )
        (self.directory / "full.log").write_text(
            "538 passed, 1 skipped, 1 warning in 31.21s\n", encoding="utf-8"
        )

    def test_partial_failure_is_not_success(self):
        report = module.inspect_run(self.directory)
        self.assertEqual(report["pytest_passed"], 538)
        self.assertEqual(report["stage_exit_codes"]["torch_probe"], 2)
        self.assertFalse(report["all_stages_passed"])

    def test_missing_stage_rejected(self):
        (self.directory / "summary.txt").write_text(
            "full: exit=0\n", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            module.inspect_run(self.directory)

    def test_missing_log_rejected(self):
        (self.directory / "full.log").unlink()
        with self.assertRaises(ValueError):
            module.inspect_run(self.directory)
