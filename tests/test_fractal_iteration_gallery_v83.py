import base64
import io
import json
import unittest
from contextlib import redirect_stdout

from PIL import Image
from klone.fractal_iteration_gallery import iteration_gallery, render_gallery, main


class FractalIterationGalleryV83(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = iteration_gallery(32)
        cls.rows = cls.report["observations"]

    def test_fixed_conditions(self):
        self.assertEqual(self.report["dimensions"], [32, 32])
        self.assertEqual([r["iterations"] for r in self.rows], [8, 24, 48, 96])

    def test_monotone_unresolved_and_deltas(self):
        self.assertIsNone(self.rows[0]["newly_resolved_since_previous"])
        for a, b in zip(self.rows, self.rows[1:]):
            self.assertLessEqual(b["unresolved_samples"], a["unresolved_samples"])
            self.assertEqual(b["newly_resolved_since_previous"],
                             a["unresolved_samples"] - b["unresolved_samples"])

    def test_sample_accounting(self):
        for row in self.rows:
            self.assertEqual(row["escaped_samples"] + row["unresolved_samples"], 1024)
            self.assertEqual(row["unresolved_fraction"], row["unresolved_samples"] / 1024)

    def test_palette_ranges(self):
        self.assertEqual(self.rows[0]["palette_total_variation_from_first"], 0)
        for row in self.rows:
            self.assertTrue(0 <= row["palette_total_variation_from_first"] <= 1)
            self.assertTrue(0 <= row["palette_entropy"]["entropy_bits"] <= 9)

    def test_previews(self):
        for row in self.rows:
            with Image.open(io.BytesIO(base64.b64decode(row["preview_png_base64"]))) as image:
                self.assertEqual((image.format, image.size), ("PNG", (32, 32)))
                image.load()

    def test_html(self):
        html = render_gallery(self.report)
        self.assertEqual(html.count("data:image/png;base64,"), 4)
        self.assertIn("Baseline", html)
        self.assertIn("Limitations", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script", html)

    def test_repeatability(self):
        self.assertEqual(self.report, iteration_gallery(32))

    def test_cli_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--size", "32"]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)

    def test_invalid_size(self):
        with self.assertRaises(ValueError):
            iteration_gallery(257)
