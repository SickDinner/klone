"""CLI compatibility tests for Termux battery output aliases."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class BatteryOutputAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "tools" / "termux_evidence_battery.py"
        spec = importlib.util.spec_from_file_location("termux_battery_cli_alias", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_output_aliases_identical(self):
        for flag in ("--output", "--output-dir"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                output = root / "out"
                with patch.object(self.module, "run_battery", return_value={"overall": "passed"}) as run:
                    with patch("builtins.print"):
                        code = self.module.main(["--root", str(root), flag, str(output)])
                self.assertEqual(code, 0)
                # Preserve the original path for the collector's no-follow checks.
                # Windows can spell the same temp directory with an 8.3 alias.
                self.assertEqual(run.call_args.args[1], output)

    def test_missing_output_rejected(self):
        with patch.object(sys, "stderr"):
            with self.assertRaises(SystemExit) as raised:
                self.module.main(["--root", "/tmp"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
