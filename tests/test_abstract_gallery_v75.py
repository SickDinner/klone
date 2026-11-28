import base64
import json
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO

from PIL import Image

from klone.abstract_gallery import abstract_gallery, render_gallery, main


class AbstractGalleryV75(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = abstract_gallery()
        cls.rows = {r["variant"]: r for r in cls.report["observations"]}

    def test_four_experiment_conditions(self):
        self.assertEqual(set(self.rows), {
            "original", "horizontal_mirror", "red_blue_swap", "grayscale"})
        self.assertEqual(self.report["dimensions"], [64, 64])

    def test_original_has_zero_distance(self):
        r = self.rows["original"]
        self.assertEqual(r["changed_pixel_fraction"], 0)
        self.assertEqual(r["palette_distance"]["total_variation_exact"], "0")

    def test_mirror_preserves_palette_but_changes_pixels(self):
        r = self.rows["horizontal_mirror"]
        self.assertEqual(r["palette_distance"]["total_variation_exact"], "0")
        self.assertGreater(r["changed_pixel_fraction"], 0)

    def test_channel_swap_changes_palette(self):
        r = self.rows["red_blue_swap"]
        self.assertEqual(r["palette_distance"]["total_variation_exact"], "1")
        self.assertEqual(r["changed_pixel_fraction"], 1)

    def test_grayscale_is_neutral(self):
        r = self.rows["grayscale"]
        self.assertEqual(r["neutral_fraction"], 1)
        self.assertGreater(r["changed_pixel_fraction"], 0)

    def test_previews_are_valid_pngs(self):
        for row in self.rows.values():
            with Image.open(BytesIO(base64.b64decode(row["preview_png_base64"]))) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.size, (64, 64))
                image.load()

    def test_static_html_contains_four_previews(self):
        html = render_gallery(self.report)
        self.assertEqual(html.count("data:image/png;base64,"), 4)
        self.assertIn("Changed pixels", html)
        self.assertIn("Limitations", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script", html)

    def test_deterministic_report(self):
        self.assertEqual(self.report, abstract_gallery())

    def test_cli_json(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(output.getvalue()), self.report)
