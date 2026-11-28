"""Structural checks only; not a browser or assistive-technology certification."""
import base64
import unittest
from html.parser import HTMLParser

from klone.creative_research_museum import research_museum, render_museum


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class CreativeMuseumAccessibilityV101(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = research_museum()
        cls.html = render_museum()
        parser = Collector()
        parser.feed(cls.html)
        cls.elements = parser.elements

    def test_section_heading_references(self):
        headings = {a["id"] for t, a in self.elements if t == "h2" and "id" in a}
        sections = [a for t, a in self.elements if t == "section"]
        self.assertEqual(len(sections), 5)
        self.assertEqual(len(headings), 5)
        self.assertEqual({a["aria-labelledby"] for a in sections}, headings)

    def test_descriptive_image_alternatives(self):
        expected = [m for r in self.report["rooms"] for m in r["media"]
                    if m["media_type"].startswith("image/")]
        images = [a for t, a in self.elements if t == "img"]
        self.assertEqual(len(images), 25)
        for attrs, item in zip(images, expected):
            self.assertEqual(attrs["alt"], item["title"] + ". " + item["description"])

    def test_language_and_focus_styles(self):
        self.assertIn(("pre", {"lang": "fi"}), self.elements)
        self.assertIn("a:focus-visible", self.html)
        self.assertIn("outline:3px solid currentColor", self.html)
        self.assertIn("min-height:44px", self.html)
        self.assertIn("overflow-wrap:anywhere", self.html)

    def test_embedded_media_preserved(self):
        expected = [m for r in self.report["rooms"] for m in r["media"]]
        actual = [(t, a) for t, a in self.elements if t in ("img", "audio")]
        self.assertEqual(len(actual), 28)
        for (tag, attrs), item in zip(actual, expected):
            prefix, payload = attrs["src"].split(",", 1)
            self.assertEqual(prefix, "data:" + item["media_type"] + ";base64")
            self.assertEqual(base64.b64decode(payload, validate=True),
                             base64.b64decode(item["media_base64"], validate=True))
            if tag == "audio":
                self.assertIn("controls", attrs)
                self.assertNotIn("autoplay", attrs)

    def test_internal_navigation(self):
        links = [a["href"] for t, a in self.elements if t == "a"]
        self.assertEqual(links, ["#" + r["id"] for r in self.report["rooms"]])
        self.assertNotIn("script", [t for t, a in self.elements])
