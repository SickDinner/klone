import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "tools" / "termux_evidence_battery.py"
spec = importlib.util.spec_from_file_location("termux_evidence_battery", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TermuxEvidenceBatteryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test",
                        "-c", "user.email=test@example.invalid", "commit",
                        "--allow-empty", "-qm", "initial"], check=True)

    def test_clean_checkout_has_commit(self):
        snapshot = module.checkout(self.root)
        self.assertEqual(len(snapshot["commit"]), 40)
        self.assertFalse(snapshot["dirty"])

    def test_dirty_checkout_detected(self):
        (self.root / "new-file").write_text("changed", encoding="utf-8")
        self.assertTrue(module.checkout(self.root)["dirty"])

    def test_missing_virtualenv_does_not_create_false_success(self):
        with self.assertRaises(FileNotFoundError):
            module.run_battery(self.root, self.root / "reports")
