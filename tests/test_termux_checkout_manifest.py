import subprocess
import unittest
from unittest.mock import patch
from klone.termux_checkout_manifest import checkout_manifest


class TermuxCheckoutManifestTests(unittest.TestCase):
    def test_clean_checkout_reports_exact_commit_without_attestation(self):
        def fake_run(args, **kwargs):
            output = "a" * 40 if args[1] == "rev-parse" else ""
            return subprocess.CompletedProcess(args, 0, stdout=output)
        with patch("klone.termux_checkout_manifest.subprocess.run", side_effect=fake_run):
            result = checkout_manifest(".")
        self.assertEqual(result["commit"], "a" * 40)
        self.assertFalse(result["dirty"])
        self.assertFalse(result["device_identity_verified"])
        self.assertFalse(result["execution_attested"])

    def test_dirty_checkout_reported(self):
        def fake_run(args, **kwargs):
            output = "b" * 40 if args[1] == "rev-parse" else " M file.py"
            return subprocess.CompletedProcess(args, 0, stdout=output)
        with patch("klone.termux_checkout_manifest.subprocess.run", side_effect=fake_run):
            self.assertTrue(checkout_manifest(".")["dirty"])

    def test_invalid_sha_rejected(self):
        with patch("klone.termux_checkout_manifest.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, stdout="short")):
            with self.assertRaises(ValueError):
                checkout_manifest(".")
