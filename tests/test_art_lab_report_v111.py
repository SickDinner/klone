"""Regression tests for the static art laboratory report."""
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from html.parser import HTMLParser

from klone.art_lab_report import main, render_report
from klone.art_synthesis_study import synthesis_study


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.pre_text = []
        self.inside_pre = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "pre":
            self.inside_pre = True
            self.pre_text.append("")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.inside_pre = False

    def handle_data(self, data):
        if self.inside_pre:
            self.pre_text[-1] += data


class ArtLabReportV111(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = synthesis_study()
        cls.html = render_report(cls.source)
        cls.doc = DocumentParser()
        cls.doc.feed(cls.html)
        cls.doc.close()

    def test_document_structure(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertTrue(self.html.endswith("</body></html>"))
        self.assertEqual(sum(t == "h1" for t,a in self.doc.tags), 1)
        self.assertEqual(sum(t == "article" for t,a in self.doc.tags), 7)

    def test_navigation_resolves(self):
        ids = [a["id"] for t,a in self.doc.tags if "id" in a]
        links = [a["href"] for t,a in self.doc.tags if t == "a"]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(links), 5)
        self.assertEqual(set(links), {"#" + i for i in ids})

    def test_summary_values(self):
        for key in ("study_count", "cross_domain_profile_count",
                    "cross_domain_pair_count", "catalog_revision_count",
                    "catalog_complete_match_count", "review_evidence_item_count"):
            self.assertIn("<strong>" + str(self.source["summary"][key]) + "</strong>",
                          self.html)

    def test_full_source_payloads_preserved(self):
        blocks = [json.loads(t) for t in self.doc.pre_text]
        for study in self.source["studies"]:
            self.assertIn(study["payload"], blocks)
            self.assertIn(study["payload_sha256"], self.html)
            self.assertIn(study["source_schema"], self.html)

    def test_evidence_and_scope_preserved(self):
        blocks = [json.loads(t) for t in self.doc.pre_text]
        review = next(r["payload"] for r in self.source["studies"] if r["version"] == "10.11")
        for claim in review["reviews"]:
            self.assertIn(claim["evidence"], blocks)
            self.assertIn(claim["id"], self.html)
        self.assertIn(self.source["scope"], blocks)
        self.assertIn("Not assessed", self.html)
        self.assertIn("Contradicted in fixtures", self.html)

    def test_no_active_or_remote_content(self):
        prohibited = {"script", "iframe", "object", "embed", "form", "link", "img"}
        for tag, attrs in self.doc.tags:
            self.assertNotIn(tag, prohibited)
            self.assertNotIn("src", attrs)
            self.assertFalse(any(k.startswith("on") for k in attrs))
            if "href" in attrs:
                self.assertTrue(attrs["href"].startswith("#"))
        csp = [a["content"] for t,a in self.doc.tags
               if t == "meta" and a.get("http-equiv") == "Content-Security-Policy"]
        self.assertEqual(len(csp), 1)
        self.assertIn("default-src 'none'", csp[0])

    def test_escape_untrusted_text(self):
        source = copy.deepcopy(self.source)
        review = next(r["payload"] for r in source["studies"] if r["version"] == "10.11")
        review["reviews"][0]["claim"] = '<script>alert("x")</script>'
        review["reviews"][0]["status"] = 'x" onclick="alert(1)'
        output = render_report(source)
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>", output)
        doc = DocumentParser()
        doc.feed(output)
        self.assertFalse(any("onclick" in a for t,a in doc.tags))

    def test_accessibility_and_mobile(self):
        self.assertIn('lang="en"', self.html)
        self.assertIn('name="viewport"', self.html)
        self.assertIn('aria-label="Report sections"', self.html)
        self.assertIn('scope="col"', self.html)
        self.assertIn("@media(max-width:480px)", self.html)
        self.assertIn("@media print", self.html)

    def test_deterministic_and_read_only(self):
        before = copy.deepcopy(self.source)
        self.assertEqual(render_report(self.source), self.html)
        self.assertEqual(self.source, before)
        self.assertEqual(render_report(synthesis_study()), self.html)

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(out.getvalue(), self.html + "\n")
