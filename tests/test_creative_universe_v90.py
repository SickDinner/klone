import base64
import copy
import io
import json
import unittest
import wave
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

from PIL import Image
from klone.creative_universe import creative_universe, render_exhibition, main


class CreativeUniverseV90(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = creative_universe()

    def test_inventory(self):
        items = self.report["exhibits"]
        self.assertEqual(len(items), 10)
        self.assertEqual(len({item["id"] for item in items}), 10)
        self.assertEqual(self.report["schema"], "klone.creative_universe_exhibition.v1")
        self.assertEqual(sum(i["media_type"] == "image/svg+xml" for i in items), 6)
        self.assertEqual(sum(i["media_type"] == "image/png" for i in items), 2)
        self.assertEqual(sum(i["media_type"] == "audio/wav" for i in items), 2)

    def test_svg_media(self):
        for item in self.report["exhibits"]:
            if item["media_type"] == "image/svg+xml":
                data = base64.b64decode(item["media_base64"], validate=True)
                root = ET.fromstring(data)
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertIsNotNone(root.find("{http://www.w3.org/2000/svg}title"))

    def test_png_media(self):
        expected = {"mandelbrot": (128, 128), "rule30": (145, 72)}
        for item in self.report["exhibits"]:
            if item["media_type"] == "image/png":
                with Image.open(io.BytesIO(base64.b64decode(item["media_base64"]))) as im:
                    self.assertEqual(im.format, "PNG")
                    self.assertEqual(im.size, expected[item["id"]])
                    im.load()

    def test_audio_media(self):
        expected = {"pulse_music": 144000, "dusk_melody": 12000}
        for item in self.report["exhibits"]:
            if item["media_type"] == "audio/wav":
                with wave.open(io.BytesIO(base64.b64decode(item["media_base64"])), "rb") as src:
                    self.assertEqual((src.getnchannels(), src.getsampwidth(), src.getframerate()),
                                     (1, 2, 16000))
                    self.assertEqual(src.getnframes(), expected[item["id"]])

    def test_html_offline(self):
        html = render_exhibition(self.report)
        self.assertEqual(html.count("<article>"), 10)
        self.assertEqual(html.count("<img "), 8)
        self.assertEqual(html.count("<audio controls"), 2)
        self.assertIn("Limitations", html)
        self.assertNotIn("autoplay", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("https://", html)

    def test_escape_text_and_reject_media_type(self):
        report = copy.deepcopy(self.report)
        report["exhibits"][0]["title"] = "<script>alert(1)</script>"
        html = render_exhibition(report)
        self.assertNotIn("<script", html)
        self.assertIn("&lt;script&gt;", html)
        report["exhibits"][0]["media_type"] = "text/html"
        with self.assertRaises(ValueError):
            render_exhibition(report)

    def test_repeatability(self):
        self.assertEqual(creative_universe(), self.report)

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
