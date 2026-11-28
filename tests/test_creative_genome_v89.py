import base64
import io
import json
import unittest
from contextlib import redirect_stdout

from PIL import Image
from klone.creative_genome import creative_genome_study, render_genome_html, main


class CreativeGenomeV89(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = creative_genome_study()
        cls.rows = {r["pattern"]: r for r in cls.report["observations"]}

    def test_fixed_patterns(self):
        self.assertEqual(self.report["dimensions"], [32, 32])
        self.assertEqual(set(self.rows), {"vertical_split", "horizontal_split",
                                         "checkerboard", "vertical_stripes"})

    def test_identical_palette(self):
        for r in self.rows.values():
            self.assertEqual(r["palette"]["occupied_bins"], 2)
            self.assertEqual(r["palette"]["entropy_bits"], 1)
            self.assertEqual(r["palette_distance_from_first"], 0)

    def test_directional_adjacency(self):
        for name, expected in (
            ("vertical_split", (1/31, 0)),
            ("horizontal_split", (0, 1/31)),
            ("checkerboard", (1, 1)),
            ("vertical_stripes", (1, 0)),
        ):
            s = self.rows[name]["spatial"]
            self.assertEqual((s["horizontal_neighbor_difference_fraction"],
                              s["vertical_neighbor_difference_fraction"]), expected)

    def test_mirror_matches(self):
        for name, expected in (
            ("vertical_split", (0, 1)),
            ("horizontal_split", (1, 0)),
            ("checkerboard", (0, 0)),
            ("vertical_stripes", (0, 1)),
        ):
            s = self.rows[name]["spatial"]
            self.assertEqual((s["left_right_mirror_match_fraction"],
                              s["top_bottom_mirror_match_fraction"]), expected)

    def test_aligned_difference(self):
        self.assertEqual(self.rows["vertical_split"]["aligned_pixel_difference_from_first"], 0)
        for name in ("horizontal_split", "checkerboard", "vertical_stripes"):
            self.assertEqual(self.rows[name]["aligned_pixel_difference_from_first"], .5)

    def test_png_previews(self):
        for r in self.rows.values():
            with Image.open(io.BytesIO(base64.b64decode(r["preview_png_base64"]))) as im:
                self.assertEqual((im.format, im.size), ("PNG", (32, 32)))
                self.assertEqual(sorted(n for n, _ in im.getcolors()), [512, 512])

    def test_html(self):
        html = render_genome_html(self.report)
        self.assertEqual(html.count("data:image/png;base64,"), 4)
        self.assertIn("Limitations", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("https://", html)

    def test_repeatability(self):
        self.assertEqual(creative_genome_study(), self.report)

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
