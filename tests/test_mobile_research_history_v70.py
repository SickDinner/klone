"""Regression checks for responsive research-history presentation."""
import unittest
from html.parser import HTMLParser

from klone.research_history import build_history, render_history_html


class ElementCounter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards = 0
        self.tables = 0

    def handle_starttag(self, tag, attrs):
        if tag == "article" and dict(attrs).get("class") == "observation":
            self.cards += 1
        if tag == "table":
            self.tables += 1


class MobileResearchHistoryV70(unittest.TestCase):
    def report(self):
        return build_history([
            {"label": "KLONE V6.9", "commit": "a" * 40, "exit_code": 0,
             "summary": "1157 passed, 1 skipped, 1 warning, 333 subtests passed in 111.92s"},
            {"label": "Unmeasured", "commit": "b" * 40},
        ])

    def test_mobile_cards_and_desktop_table(self):
        html = render_history_html(self.report())
        parser = ElementCounter()
        parser.feed(html)
        self.assertEqual(parser.cards, 2)
        self.assertEqual(parser.tables, 1)
        self.assertIn("@media(min-width:64rem)", html)
        self.assertIn(".table-wrap{display:none;overflow-x:auto}", html)
        self.assertIn(".observations{display:none}", html)

    def test_mobile_grid_and_commit_wrap(self):
        html = render_history_html(self.report())
        self.assertIn("repeat(2,minmax(0,1fr))", html)
        self.assertIn(".commit dd{font: .85rem/1.5 monospace;overflow-wrap:anywhere}", html)
        self.assertIn("min-width:74rem", html)

    def test_mobile_metrics_and_full_commit(self):
        html = render_history_html(self.report())
        for pair in ("<dt>Passed</dt><dd>1157</dd>",
                     "<dt>Subtests passed</dt><dd>333</dd>",
                     "<dt>Warnings</dt><dd>1</dd>",
                     "<dt>Duration (s)</dt><dd>111.92</dd>",
                     "<dt>Claimed commit</dt><dd>" + "a" * 40 + "</dd>"):
            self.assertIn(pair, html)

    def test_missing_values_are_explicit(self):
        html = render_history_html(self.report())
        self.assertIn("<dt>Passed</dt><dd>Not recorded</dd>", html)
        self.assertIn("<dt>Subtests passed</dt><dd>Not recorded</dd>", html)

    def test_mobile_label_escaped(self):
        report = self.report()
        report["entries"][0]["label"] = "<script>alert(1)</script>"
        html = render_history_html(report)
        self.assertIn("<h2>&lt;script&gt;alert(1)&lt;/script&gt;</h2>", html)
        self.assertNotIn("<script>", html)

    def test_no_remote_assets_and_original_evidence(self):
        html = render_history_html(self.report())
        self.assertNotIn("https://", html)
        self.assertIn("not independently verified", html)
        self.assertIn("passed_with_exclusions", html)
