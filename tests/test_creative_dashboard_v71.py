import copy
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image
from klone.creative_project_report import creative_project_report, main
from klone.creative_dashboard import render_creative_dashboard


class CreativeDashboardV71(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.art = root / "art.png"
        self.music = root / "music.wav"
        self.lyrics = root / "lyrics.txt"
        Image.new("RGB", (32, 32), "red").save(self.art)
        self.lyrics.write_text("[Verse]\nPohjoinen yö", encoding="utf-8")
        with wave.open(str(self.music), "wb") as out:
            out.setparams((1, 2, 8192, 0, "NONE", "not compressed"))
            out.writeframes(bytes(2048))

    def report(self):
        return creative_project_report(self.art, self.music, self.lyrics)

    def test_three_panels(self):
        html = render_creative_dashboard(self.report())
        for heading in ("Artwork", "Music clip", "Written verse"):
            self.assertIn("<h2>" + heading + "</h2>", html)
        self.assertIn("@media(min-width:64rem)", html)
        self.assertIn("color-scheme:light dark", html)

    def test_silence_not_rendered_as_zero(self):
        html = render_creative_dashboard(self.report())
        self.assertIn("Not available", html)
        self.assertNotIn("<meter ", html)

    def test_zero_fraction_is_a_measurement(self):
        report = self.report()
        report["music_clip"]["channels"][0]["band_fractions"][0]["fraction"] = 0.0
        html = render_creative_dashboard(report)
        self.assertIn("value='0.0'", html)
        self.assertIn("0.00%", html)

    def test_palette_is_labeled(self):
        html = render_creative_dashboard(self.report())
        self.assertIn("RGB bin [7, 0, 0]", html)
        self.assertIn("100.00%", html)

    def test_reject_invalid_rgb_or_fraction(self):
        report = self.report()
        report["artwork"]["dominant_bins"][0]["rgb_bin"] = [0, 0, 8]
        with self.assertRaises(ValueError):
            render_creative_dashboard(report)
        report = self.report()
        report["artwork"]["neutral_fraction"] = float("nan")
        with self.assertRaises(ValueError):
            render_creative_dashboard(report)

    def test_escape_and_no_external_assets(self):
        report = self.report()
        report["limitations"].append("<script>alert(1)</script>")
        html = render_creative_dashboard(report)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("Pohjoinen yö", html)

    def test_repeatable_read_only_render(self):
        report = self.report()
        before = copy.deepcopy(report)
        self.assertEqual(render_creative_dashboard(report), render_creative_dashboard(report))
        self.assertEqual(before, report)

    def test_cli_html(self):
        out = StringIO()
        with redirect_stdout(out):
            code = main(["--artwork", str(self.art), "--music-clip", str(self.music),
                         "--lyrics", str(self.lyrics), "--format", "html"])
        self.assertEqual(code, 0)
        self.assertIn("<!doctype html>", out.getvalue())
