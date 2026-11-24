"""Unit tests for bounded SQLite warning attribution (no real KLONE DB)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import warnings
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "tools" / "trace_sqlite_resources_v341.py"
SPEC = importlib.util.spec_from_file_location("klone_trace_sqlite_resources_v341", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SQLiteResourceTraceV341Tests(unittest.TestCase):
    def test_group_allowlist(self):
        self.assertEqual(len(MODULE.source_patterns("memory")), 10)
        self.assertEqual(len(MODULE.source_patterns("research")), 5)
        self.assertEqual(len(MODULE.source_patterns("approval")), 5)
        self.assertEqual(len(MODULE.source_patterns("all")), 20)

    def test_unknown_group_is_denied(self):
        with self.assertRaises(ValueError):
            MODULE.source_patterns("../test_*.py")

    def test_all_is_deterministic_and_unique(self):
        self.assertEqual(MODULE.source_patterns("all"), MODULE.source_patterns("all"))
        self.assertEqual(len(MODULE.source_patterns("all")),
                         len(set(MODULE.source_patterns("all"))))

    def test_invalid_commit_denied_before_git(self):
        for value in ("", "x" * 40, "a" * 39, "a" * 41, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.assert_exact_checkout(Path("."), value)

    def test_commit_match_and_mismatch(self):
        from subprocess import CompletedProcess
        with patch.object(MODULE.subprocess, "run", return_value=CompletedProcess(
                args=[], returncode=0, stdout="a" * 40 + "\n")):
            MODULE.assert_exact_checkout(Path("."), "a" * 40)
            with self.assertRaises(ValueError):
                MODULE.assert_exact_checkout(Path("."), "b" * 40)

    def test_warning_classification(self):
        self.assertEqual(MODULE._classify(ResourceWarning("unclosed database in <sqlite3.Connection ...>")),
                         "sqlite_connection_unclosed")
        self.assertEqual(MODULE._classify(ResourceWarning("unclosed file with private secret")),
                         "other_resource_warning")

    def test_clean_warning_list_is_not_attestation(self):
        r = MODULE.summarize_warnings([])
        self.assertEqual(r["resource_warning_count"], 0)
        self.assertFalse(r["warning_absence_proves_no_leak"])

    def test_warning_text_is_never_leaked(self):
        secret = "SQL_PRIVATE_NEVER_OUTPUT"
        with warnings.catch_warnings(record=True) as rows:
            warnings.simplefilter("always", ResourceWarning)
            warnings.warn("unclosed database " + secret, ResourceWarning)
        r = MODULE.summarize_warnings(rows)
        self.assertEqual(r["sqlite_connection_warning_count"], 1)
        self.assertNotIn(secret, str(r))
        self.assertEqual(len(r["warnings"]), 1)

    def test_non_resource_warning_ignored(self):
        with warnings.catch_warnings(record=True) as rows:
            warnings.simplefilter("always")
            warnings.warn("a deprecation", DeprecationWarning)
        self.assertEqual(MODULE.summarize_warnings(rows)["resource_warning_count"], 0)

    def test_warning_limit(self):
        with warnings.catch_warnings(record=True) as rows:
            warnings.simplefilter("always", ResourceWarning)
            for i in range(8):
                warnings.warn("file unclosed", ResourceWarning)
        r = MODULE.summarize_warnings(rows, max_items=2)
        self.assertEqual(r["resource_warning_count"], 8)
        self.assertEqual(len(r["warnings"]), 2)
        self.assertTrue(r["warning_output_truncated"])

    def test_invalid_limits_denied(self):
        with self.assertRaises(ValueError):
            MODULE.summarize_warnings([], max_items=0)
        with warnings.catch_warnings(record=True) as rows:
            warnings.simplefilter("always", ResourceWarning)
            warnings.warn("unclosed database", ResourceWarning)
        with self.assertRaises(ValueError):
            MODULE.summarize_warnings(rows, max_frames=0)

    def test_runner_discovers_real_unittest_and_captures_resource_warning(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "src").mkdir()
            (root / "tests" / "test_fixture_probe.py").write_text(
                "import unittest, warnings\n"
                "class FixtureProbe(unittest.TestCase):\n"
                "    def test_warning(self):\n"
                "        warnings.warn(\"unclosed database in <sqlite3.Connection>\", ResourceWarning)\n"
            )
            with patch.object(MODULE, "ROOT", root), patch.dict(
                    MODULE.GROUPS, {"fixture_probe": ("test_fixture_probe.py",)}), patch.object(
                    MODULE, "assert_exact_checkout"):
                result = MODULE.run_group(group="fixture_probe", expected_sha="a"*40)
            self.assertEqual(result["test_count"], 1)
            self.assertTrue(result["tests_successful"])
            self.assertEqual(result["resource_warning_count"], 1)
            self.assertEqual(result["sqlite_connection_warning_count"], 1)
            self.assertFalse(result["source_origin_authenticated"])
            self.assertFalse(result["memory_write_authorized"])

    def test_no_files_or_databases_touched_by_summary(self):
        with tempfile.TemporaryDirectory() as d:
            before = list(Path(d).iterdir())
            MODULE.summarize_warnings([])
            self.assertEqual(before, list(Path(d).iterdir()))


if __name__ == "__main__":
    unittest.main()
