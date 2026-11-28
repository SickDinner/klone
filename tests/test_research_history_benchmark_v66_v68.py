"""Synthetic history and artwork measurement checks."""
import copy
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from klone.research_history import build_history, render_history_html, main
from klone.artwork_benchmark import benchmark_artwork


class ResearchHistoryV66(unittest.TestCase):
    def entries(self):
        return [
            {"label": "earlier", "commit": "a" * 40, "exit_code": 0,
             "summary": "1128 passed, 1 skipped in 95.55s"},
            {"label": "later", "commit": "b" * 40, "exit_code": 1,
             "summary": "1128 passed, 1 failed in 106.81s"},
            {"label": "not yet measured", "commit": "c" * 40},
        ]

    def test_evidence_and_input_order(self):
        entries = self.entries()
        before = copy.deepcopy(entries)
        r = build_history(entries)
        self.assertEqual(entries, before)
        self.assertEqual([x["label"] for x in r["entries"]],
                         ["earlier", "later", "not yet measured"])
        self.assertFalse(r["entries"][0]["observation"]["independently_verified"])
        self.assertEqual(r["entries"][1]["observation"]["status"], "not_passed")

    def test_missing_not_zero(self):
        r = build_history(self.entries())
        self.assertIsNone(r["entries"][2]["observation"])
        self.assertIn("Not recorded", render_history_html(r))

    def test_escape_and_no_remote_assets(self):
        entries = self.entries()
        entries[0]["label"] = "<script>alert(1)</script>"
        page = render_history_html(build_history(entries))
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertNotIn("https://", page)

    def test_invalid_entries(self):
        for entries in ([], [{}], [None], self.entries() * 34,
                        [{"label": "x", "commit": 123}],
                        [{"label": "x", "commit": "a" * 40, "exit_code": 0}]):
            with self.subTest(entries_type=type(entries).__name__):
                with self.assertRaises(ValueError):
                    build_history(entries)

    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "history.json"
            path.write_text(json.dumps(self.entries()), encoding="utf-8")
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(main([str(path), "--format", "json"]), 0)
            self.assertEqual(json.loads(out.getvalue()), build_history(self.entries()))

    def test_html_columns_and_failure_visible(self):
        page = render_history_html(build_history(self.entries()))
        self.assertIn("<th scope='col'>Failed</th>", page)
        self.assertIn("not_passed", page)
        self.assertIn("not independently verified", page)


class ArtworkBenchmarkV68(unittest.TestCase):
    def test_invalid_repetitions(self):
        for count in (1, 11, True, 2.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                benchmark_artwork(count)

    def test_reject_active_trace(self):
        with patch("klone.artwork_benchmark.tracemalloc.is_tracing", return_value=True):
            with self.assertRaises(ValueError):
                benchmark_artwork(2)

    def test_real_synthetic_fixture(self):
        r = benchmark_artwork(2)
        self.assertTrue(r["fixture_results_equal"])
        self.assertEqual(r["repetitions_per_measurement"], 2)
        for field in ("wall_time_ns", "python_traced_peak_bytes"):
            values = r[field]["samples"]
            self.assertEqual(len(values), 2)
            self.assertTrue(all(v >= 0 for v in values))
            self.assertEqual(r[field]["median"], sum(values) / 2)
        self.assertIn("not total process RSS", " ".join(r["limitations"]))

    def test_detect_changed_fixture_result(self):
        with patch("klone.artwork_benchmark.artwork_color_metrics",
                   side_effect=[{"x": 1}, {"x": 2}]):
            with self.assertRaises(RuntimeError):
                benchmark_artwork(2)
