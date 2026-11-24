"""Synthetic-only v3.4.2 tracer tests; no production DB, network or process."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
import warnings
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("klone_sqlite_full_trace_v342",
                                             TOOLS / "trace_sqlite_full_v342.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SHA = "a" * 40


class _Fixtures:
    class Good(unittest.TestCase):
        def test_ok(self):
            self.assertEqual(2 + 2, 4)


    class LeakyWarning(unittest.TestCase):
        def test_warning(self):
            warnings.warn("unclosed database in <sqlite3.Connection object>",
                          ResourceWarning, stacklevel=1)


    class Failure(unittest.TestCase):
        def test_bad(self):
            self.fail("private fixture: do not export")


    class Printing(unittest.TestCase):
        def test_noisy(self):
            print("private stdout: do not export")
            self.assertTrue(True)


class FakeLoader:
    def __init__(self, *types):
        self.types = types
        self.calls = []

    def discover(self, start_dir, pattern):
        self.calls.append((start_dir, pattern))
        s = unittest.TestSuite()
        for typ in self.types:
            s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(typ))
        return s


class SQLiteFullTraceV342Tests(unittest.TestCase):
    def run_trace(self, *cases, expected_count=None):
        loader = FakeLoader(*(cases or (_Fixtures.Good,)))
        with patch.object(MODULE, "assert_exact_checkout", return_value=None):
            report = MODULE.run_full_trace(expected_sha=SHA,
                                           expected_count=expected_count,
                                           _loader=loader)
        return report, loader

    def test_accepts_unpinned_count(self):
        report, _ = self.run_trace(_Fixtures.Good)
        self.assertEqual(report["test_count"], 1)
        self.assertIsNone(report["expected_test_count"])
        self.assertFalse(report["test_count_pin_matched"])

    def test_exact_pinned_count(self):
        report, _ = self.run_trace(_Fixtures.Good, expected_count=1)
        self.assertTrue(report["test_count_pin_matched"])
        self.assertEqual(MODULE.report_exit_code(report), 0)

    def test_wrong_count_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "test_count_does_not_match_requested_pin"):
            self.run_trace(_Fixtures.Good, expected_count=2)

    def test_full_unittest_discovery_not_20_module_selection(self):
        report, loader = self.run_trace(_Fixtures.Good)
        self.assertEqual(loader.calls[0][1], "test_*.py")
        self.assertEqual(report["suite_scope"], "all_repository_test_py_modules")

    def test_resource_warning_captured(self):
        report, _ = self.run_trace(_Fixtures.LeakyWarning)
        self.assertEqual(report["resource_warning_count"], 1)
        self.assertEqual(report["sqlite_connection_warning_count"], 1)
        self.assertEqual(report["warnings"][0]["kind"], "sqlite_connection_unclosed")
        self.assertEqual(MODULE.report_exit_code(report), 3)

    def test_test_failure_is_distinct_from_resource_warning(self):
        report, _ = self.run_trace(_Fixtures.Failure)
        self.assertEqual(MODULE.report_exit_code(report), 2)
        self.assertFalse(report["tests_successful"])
        self.assertEqual(report["test_failure_count"], 1)

    def test_raw_test_output_not_exported(self):
        report, _ = self.run_trace(_Fixtures.Failure, _Fixtures.Printing)
        data = json.dumps(report)
        self.assertNotIn("private", data)
        self.assertFalse(report["test_output_exported"])

    def test_count_must_be_positive_nonboolean(self):
        for value in (True, False, -1, 0, 10001, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.validate_expected_count(value)

    def test_trace_frames_bounded(self):
        for frames in (0, 4, 26, 999, True, 1.5):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                MODULE.run_full_trace(
                    expected_sha=SHA, max_frames=frames,
                    _checkout_validator=lambda *_: None, _loader=FakeLoader(_Fixtures.Good))

    def test_report_hash_is_present_and_repeatable(self):
        first, _ = self.run_trace(_Fixtures.Good)
        second, _ = self.run_trace(_Fixtures.Good)
        self.assertEqual(first, second)
        self.assertEqual(len(first["report_sha256"]), 64)

    def test_no_approval_provenance_or_restart(self):
        report, _ = self.run_trace(_Fixtures.Good)
        self.assertFalse(report["approval_granted"])
        self.assertFalse(report["source_origin_authenticated"])
        self.assertFalse(report["service_restart_performed_by_tracer"])
        self.assertFalse(report["warning_absence_proves_no_leak"])
        self.assertFalse(report["production_database_selected_by_tracer"])

    def test_report_exit_fails_for_incomplete_run(self):
        report, _ = self.run_trace(_Fixtures.Good)
        report["tests_ran"] = 0
        self.assertEqual(MODULE.report_exit_code(report), 2)

    def test_tracer_does_not_stop_preexisting_tracemalloc(self):
        import tracemalloc
        tracemalloc.start(5)
        try:
            self.run_trace(_Fixtures.Good)
            self.assertTrue(tracemalloc.is_tracing())
        finally:
            tracemalloc.stop()

    def test_json_output_carries_no_unsafe_warning_message(self):
        report, _ = self.run_trace(_Fixtures.LeakyWarning)
        self.assertNotIn("unclosed database", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
