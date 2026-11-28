import copy
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image
from klone.artwork_color_metrics import artwork_color_metrics
from klone.artwork_palette_study import compare_full_histograms, palette_study, main


class ArtworkPaletteStudyV72(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def image(self, name, colors):
        path = self.root / (name + ".png")
        image = Image.new("RGB", (len(colors), 1))
        image.putdata(colors)
        image.save(path)
        return path

    def histogram(self, colors):
        path = self.image("hist", colors)
        return artwork_color_metrics(path, full_histogram=True)["full_histogram"]

    def test_default_report_unchanged(self):
        path = self.image("a", [(32, 64, 96)])
        self.assertNotIn("full_histogram", artwork_color_metrics(path))

    def test_more_than_eight_bins(self):
        colors = [(i % 8 * 32, i // 8 * 32, 0) for i in range(12)]
        path = self.image("a", colors)
        report = artwork_color_metrics(path, full_histogram=True)
        self.assertEqual(len(report["dominant_bins"]), 8)
        self.assertEqual(len(report["full_histogram"]["bins"]), 12)
        self.assertEqual(sum(b["count"] for b in report["full_histogram"]["bins"]), 12)

    def test_exact_distance(self):
        red, blue = (255, 0, 0), (0, 0, 255)
        a = self.histogram([red, red, blue])
        b = self.histogram([red, blue, blue])
        result = compare_full_histograms(a, b)
        self.assertEqual(result["total_variation_exact"], "1/3")
        self.assertEqual(result["total_variation"], 0.33333333)
        self.assertEqual(result, compare_full_histograms(b, a))

    def test_same_proportions_different_sizes(self):
        red, blue = (255, 0, 0), (0, 0, 255)
        a = self.histogram([red, blue])
        b = self.histogram([red, blue] * 3)
        self.assertEqual(compare_full_histograms(a, b)["total_variation_exact"], "0")

    def test_disjoint_palettes(self):
        a = self.histogram([(255, 0, 0)])
        b = self.histogram([(0, 0, 255)])
        self.assertEqual(compare_full_histograms(a, b)["total_variation_exact"], "1")

    def test_multicolor_comparison(self):
        colors = [(i % 8 * 32, i // 8 * 32, 0) for i in range(12)]
        a = self.image("a", colors)
        b = self.image("b", list(reversed(colors)))
        r = palette_study(a, b)
        self.assertEqual(r["comparison"]["total_variation"], 0)
        self.assertEqual(r["comparison"]["shared_occupied_bins"], 12)

    def test_reject_invalid_counts_and_duplicate_bins(self):
        a = self.histogram([(0, 0, 0)])
        for bad in (
            {**a, "sample_pixels": 2},
            {**a, "bins": a["bins"] * 2},
            {**a, "bins": [{"rgb_bin": [8, 0, 0], "count": 1}]},
            {**a, "bins": [{"rgb_bin": [0, 0, 0], "count": True}]},
        ):
            with self.assertRaises(ValueError):
                compare_full_histograms(a, bad)

    def test_read_only_and_repeatable(self):
        a = self.image("a", [(0, 0, 0)])
        b = self.image("b", [(255, 255, 255)])
        original = (a.read_bytes(), b.read_bytes())
        result = palette_study(a, b)
        self.assertEqual(result, palette_study(a, b))
        self.assertEqual(original, (a.read_bytes(), b.read_bytes()))
        h = result["before"]["full_histogram"]
        before = copy.deepcopy(h)
        compare_full_histograms(h, h)
        self.assertEqual(before, h)

    def test_cli_json(self):
        a = self.image("a", [(0, 0, 0)])
        b = self.image("b", [(255, 255, 255)])
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([str(a), str(b)]), 0)
        self.assertEqual(json.loads(out.getvalue())["comparison"]["total_variation"], 1)
