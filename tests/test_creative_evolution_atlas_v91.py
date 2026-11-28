import base64
import io
import json
import unittest
from contextlib import redirect_stdout

from PIL import Image
from klone.creative_evolution_atlas import evolution_atlas, render_atlas, main


class CreativeEvolutionAtlasV91(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evolution_atlas()
        cls.rows = cls.report["observations"]

    def test_fixed_conditions(self):
        self.assertEqual(self.report["dimensions"], [64, 64])
        self.assertEqual([r["offset_pixels"] for r in self.rows], [0, 4, 8, 16])

    def test_invariant_palette(self):
        for r in self.rows:
            self.assertEqual(r["palette_distance_from_first"], 0)
            self.assertEqual(r["palette"], self.rows[0]["palette"])
            self.assertEqual(r["palette"]["occupied_bins"], 2)
            self.assertAlmostEqual(r["palette"]["entropy_bits"], .54356444)

    def test_changed_pixel_counts(self):
        self.assertEqual([r["changed_pixels_from_first"] for r in self.rows],
                         [0, 256, 512, 1024])

    def test_changed_pixel_fractions(self):
        self.assertEqual([r["changed_pixel_fraction"] for r in self.rows],
                         [0, .0625, .125, .25])

    def test_png_previews(self):
        for r in self.rows:
            with Image.open(io.BytesIO(base64.b64decode(r["preview_png_base64"]))) as im:
                self.assertEqual((im.format, im.size), ("PNG", (64, 64)))
                self.assertEqual(sorted(n for n, _ in im.getcolors()), [512, 3584])

    def test_html_offline(self):
        html = render_atlas(self.report)
        self.assertEqual(html.count("data:image/png;base64,"), 4)
        self.assertIn("Limitations", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("https://", html)

    def test_repeatability(self):
        self.assertEqual(evolution_atlas(), self.report)

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
