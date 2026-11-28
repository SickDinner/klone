import json
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image
from klone.artwork_color_metrics import artwork_color_metrics
from klone.creative_project_report import compare_palettes, creative_project_report, main


class CreativeProjectV64V65(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.art = self.root / "art.png"
        self.music = self.root / "music.wav"
        self.lyrics = self.root / "lyrics.txt"
        Image.new("RGB", (32, 32), "red").save(self.art)
        self.lyrics.write_text("[Verse]\nPohjoinen yö", encoding="utf-8")
        with wave.open(str(self.music), "wb") as out:
            out.setparams((1, 2, 8192, 0, "NONE", "not compressed"))
            out.writeframes(bytes(2048))

    def test_same_palette(self):
        r = artwork_color_metrics(self.art)
        self.assertEqual(compare_palettes(r, r)["total_variation"], 0)

    def test_disjoint_palettes(self):
        a = artwork_color_metrics(self.art)
        Image.new("RGB", (32, 32), "blue").save(self.art)
        b = artwork_color_metrics(self.art)
        self.assertEqual(compare_palettes(a, b)["total_variation"], 1)

    def test_partial_histogram_not_compared(self):
        a = artwork_color_metrics(self.art)
        image = Image.new("RGB", (9, 1))
        for i in range(9):
            image.putpixel((i, 0), (i % 8 * 32, i // 8 * 32, 0))
        image.save(self.art)
        b = artwork_color_metrics(self.art)
        self.assertEqual(b["occupied_rgb_bins"], 9)
        self.assertIsNone(compare_palettes(a, b)["total_variation"])

    def test_combined_report_read_only_and_repeatable(self):
        paths = [self.art, self.music, self.lyrics]
        originals = [p.read_bytes() for p in paths]
        r = creative_project_report(*paths)
        self.assertEqual(r["artwork"]["neutral_fraction"], 0)
        self.assertEqual(r["verse"]["written_vowel_groups_per_line"], [4])
        self.assertIsNone(r["music_clip"]["channels"][0]["spectral_centroid_hz"])
        self.assertEqual(r, creative_project_report(*paths))
        self.assertEqual(originals, [p.read_bytes() for p in paths])

    def test_cli_json(self):
        output = StringIO()
        with redirect_stdout(output):
            code = main(["--artwork", str(self.art), "--music-clip", str(self.music),
                         "--lyrics", str(self.lyrics)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["schema"],
                         "klone.creative_project_report.v1")
