"""Snapshot-consistency tests for the local creative laboratory."""
from contextlib import redirect_stdout, redirect_stderr
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klone.local_creative_archive import creative_archive
from klone.local_art_comparison import compare_artworks
from klone.local_creative_lab_report import build_lab, main


class Payloads(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.active = False
        self.blocks = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.active = True
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.blocks[-1] += data

    def report(self, schema):
        return next(r for r in map(json.loads, self.blocks)
                    if r.get("schema") == schema)


class CreativeLabSnapshotV121(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.a = self.root / "a.txt"
        self.b = self.root / "b.txt"
        self.a.write_text("Yö saapuu\n", encoding="utf-8")
        self.b.write_text("Yö saapuu\nTuuli kulkee\n", encoding="utf-8")
        self.items = [("lyrics", self.a), ("lyrics", self.b)]
        self.pairs = [("lyrics", self.a, self.b)]

    def test_comparison_matches_standalone(self):
        expected = compare_artworks("lyrics", self.a, self.b)
        html, failed = build_lab(self.items, self.pairs)
        self.assertEqual(failed, 0)
        self.assertEqual(Payloads(html).report("klone.local_art_comparison.v1"), expected)

    def test_no_reread_after_collection(self):
        expected = compare_artworks("lyrics", self.a, self.b)
        def changed(items):
            archive = creative_archive(items)
            self.b.write_text("Changed after collection", encoding="utf-8")
            self.a.unlink()
            return archive
        with patch("klone.local_creative_lab_report.creative_archive", side_effect=changed):
            html, failed = build_lab(self.items, self.pairs)
        self.assertEqual(failed, 0)
        p = Payloads(html)
        comparison = p.report("klone.local_art_comparison.v1")
        self.assertEqual(comparison, expected)
        records = {r["record_id"]: r for r in p.report("klone.local_creative_archive.v1")["records"]}
        for side in ("first_record", "second_record"):
            ref = comparison[side]
            self.assertEqual(ref["report_sha256"], records[ref["record_id"]]["report_sha256"])

    def test_unselected_endpoint_rejected_before_analysis(self):
        with patch("klone.local_creative_lab_report.creative_archive") as analyze:
            with self.assertRaisesRegex(ValueError, "must be selected"):
                build_lab(self.items[:1], self.pairs)
            analyze.assert_not_called()

    def test_medium_must_match_selection(self):
        with self.assertRaisesRegex(ValueError, "must be selected"):
            build_lab(self.items, [("audio", self.a, self.b)])

    def test_repeated_path_changed_rejected(self):
        # Deliberately simulate two different captured reports for the same selection.
        archive = creative_archive(self.items)
        with patch("klone.local_creative_lab_report.creative_archive", return_value=archive):
            with self.assertRaisesRegex(ValueError, "changed during analysis"):
                build_lab([self.items[0], self.items[0]])

    def test_duplicate_unchanged_and_self_comparison(self):
        html, failed = build_lab([self.items[0]]*2, [("lyrics", self.a, self.a)])
        self.assertEqual(failed, 0)
        p = Payloads(html)
        self.assertEqual(p.report("klone.local_creative_archive.v1")["inventory"]["duplicate_selection_count"], 1)
        self.assertTrue(p.report("klone.local_art_comparison.v1")["same_source_bytes"])

    def test_visible_limits_and_status(self):
        html, failed = build_lab(self.items, self.pairs)
        self.assertEqual(failed, 0)
        for label in ("V12.1", "Method limitations", "Validation totals",
                      "Length-sensitive descriptive statistic", "Comparisons reuse selected artwork records"):
            self.assertIn(label, html)

    def test_cli_unselected_endpoint_no_html(self):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            main(["--item", "lyrics", str(self.a),
                  "--compare", "lyrics", str(self.a), str(self.b)])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("must be selected", err.getvalue())
