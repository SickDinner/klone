import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from klone.termux_pinned_runner import run_pinned_tests


class TermuxPinnedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "pyproject.toml").write_text("[project]\nname='test'\n")
        python = self.root / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.touch()
        self.clean = {"commit": "a" * 40, "dirty": False}
        self.dirty = {"commit": "a" * 40, "dirty": True}

    def tearDown(self):
        self.tmp.cleanup()

    def test_successful_stable_checkout(self):
        with patch("klone.termux_pinned_runner.checkout_manifest", side_effect=[
            self.clean, self.clean
        ]), patch("klone.termux_pinned_runner.subprocess.run",
                 return_value=subprocess.CompletedProcess([], 0, "OK", "")):
            result = run_pinned_tests(self.root)
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["device_identity_verified"])

    def test_dirty_checkout_skips_test_execution(self):
        with patch("klone.termux_pinned_runner.checkout_manifest",
                   return_value=self.dirty), patch(
                       "klone.termux_pinned_runner.subprocess.run") as execute:
            result = run_pinned_tests(self.root)
        self.assertEqual(result["status"], "rejected_dirty_checkout")
        execute.assert_not_called()

    def test_changed_checkout_rejected(self):
        changed = {"commit": "b" * 40, "dirty": False}
        with patch("klone.termux_pinned_runner.checkout_manifest", side_effect=[
            self.clean, changed
        ]), patch("klone.termux_pinned_runner.subprocess.run",
                 return_value=subprocess.CompletedProcess([], 0, "OK", "")):
            result = run_pinned_tests(self.root)
        self.assertEqual(result["status"], "rejected_checkout_changed")

    def test_test_failure_is_not_success(self):
        with patch("klone.termux_pinned_runner.checkout_manifest", side_effect=[
            self.clean, self.clean
        ]), patch("klone.termux_pinned_runner.subprocess.run",
                 return_value=subprocess.CompletedProcess([], 1, "", "failure")):
            result = run_pinned_tests(self.root)
        self.assertEqual(result["status"], "failed")
