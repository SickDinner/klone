import base64
import io
import json
import unittest
import wave
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from html.parser import HTMLParser

from PIL import Image
from klone.creative_research_museum import research_museum, render_museum, main


class MuseumHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.append((tag, dict(attrs)))


class CreativeResearchMuseumV98(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = research_museum()
        cls.rooms = cls.report["rooms"]
        cls.media = [m for room in cls.rooms for m in room["media"]]
        cls.panels = {p["id"]: p for room in cls.rooms for p in room["panels"]}
        cls.html = render_museum()

    def test_inventory(self):
        self.assertEqual(self.report["schema"], "klone.creative_research_museum.v1")
        self.assertEqual([r["id"] for r in self.rooms],
                         ["mathematics", "music", "variations", "synesthesia", "research"])
        self.assertEqual([len(r["media"]) for r in self.rooms], [8, 2, 16, 2, 0])
        self.assertEqual(len({m["id"] for m in self.media}), 28)
        self.assertEqual(len(self.panels), 3)

    def test_media_types(self):
        for medium, count in (("image/svg+xml", 7), ("image/png", 18), ("audio/wav", 3)):
            self.assertEqual(sum(m["media_type"] == medium for m in self.media), count)

    def test_image_integrity(self):
        for m in self.media:
            data = base64.b64decode(m["media_base64"], validate=True)
            if m["media_type"] == "image/svg+xml":
                self.assertEqual(ET.fromstring(data).tag, "{http://www.w3.org/2000/svg}svg")
            elif m["media_type"] == "image/png":
                with Image.open(io.BytesIO(data)) as im:
                    self.assertEqual(im.format, "PNG")
                    im.load()

    def test_audio_integrity(self):
        expected = {"pulse_music": 144000, "dusk_melody": 12000, "prelude-wav": 32000}
        for m in self.media:
            if m["media_type"] == "audio/wav":
                with wave.open(io.BytesIO(base64.b64decode(m["media_base64"])), "rb") as src:
                    self.assertEqual((src.getnchannels(), src.getsampwidth(), src.getframerate()),
                                     (1, 2, 16000))
                    self.assertEqual(src.getnframes(), expected[m["id"]])

    def test_research_panels(self):
        self.assertEqual(dict(self.panels["poetry"]["facts"]),
                         {"Lines": 4, "Words": 14, "Written vowel groups": 29})
        self.assertEqual(dict(self.panels["metrics"]["facts"]),
                         {"pixel_entropy": 4, "conditional_entropy": 7,
                          "mutual_information": 10, "directional_pair_counts": 10})
        self.assertEqual(dict(self.panels["tuning"]["facts"])["octave"], 0)

    def test_offline_navigation(self):
        parsed = MuseumHTML()
        parsed.feed(self.html)
        self.assertEqual(parsed.tags.count("article"), 31)
        self.assertEqual(parsed.tags.count("img"), 25)
        self.assertEqual(parsed.tags.count("audio"), 3)
        self.assertNotIn("script", parsed.tags)
        self.assertNotIn("iframe", parsed.tags)
        sections = {a["id"] for tag, a in parsed.attrs if tag == "section"}
        self.assertEqual({a["href"][1:] for tag, a in parsed.attrs if tag == "a"}, sections)
        for tag, attrs in parsed.attrs:
            if tag in ("img", "audio"):
                self.assertTrue(attrs["src"].startswith("data:"))
                self.assertNotIn("autoplay", attrs)

    def test_repeatability(self):
        self.assertEqual(research_museum(), self.report)
        self.assertEqual(render_museum(), self.html)

    def test_cli_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
