import copy
import json
import math
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image
from klone.artwork_palette_entropy import (
    palette_entropy, compare_palette_entropy, artwork_entropy_study, main,
)


def histogram(counts):
    return {
        "schema": "klone.sampled_rgb_counts.v1",
        "sample_pixels": sum(counts),
        "bins": [
            {"rgb_bin": [i // 64, (i // 8) % 8, i % 8], "count": c}
            for i, c in enumerate(counts) if c
        ],
    }


class ArtworkEntropyV76(unittest.TestCase):
    def test_single_bin(self):
        r = palette_entropy(histogram([10]))
        self.assertEqual(r["entropy_bits"], 0)
        self.assertEqual(r["effective_color_bins"], 1)

    def test_uniform_bins(self):
        r = palette_entropy(histogram([1] * 512))
        self.assertEqual(r["entropy_bits"], 9)
        self.assertEqual(r["effective_color_bins"], 512)
        self.assertEqual(r["entropy_fraction_of_512_bin_maximum"], 1)

    def test_unequal_distribution(self):
        r = palette_entropy(histogram([3, 1]))
        expected = -.75 * math.log2(.75) - .25 * math.log2(.25)
        self.assertAlmostEqual(r["entropy_bits"], expected, places=7)
        self.assertLess(r["effective_color_bins"], 2)

    def test_identical_proportions(self):
        r = compare_palette_entropy(histogram([2, 3]), histogram([4, 6]))
        self.assertEqual(r["jensen_shannon_divergence_bits"], 0)
        self.assertEqual(r["jensen_shannon_distance"], 0)
        self.assertEqual(r["total_variation"], 0)

    def test_disjoint_palettes(self):
        r = compare_palette_entropy(histogram([1, 0]), histogram([0, 1]))
        self.assertEqual(r["jensen_shannon_divergence_bits"], 1)
        self.assertEqual(r["jensen_shannon_distance"], 1)

    def test_partial_overlap(self):
        a, b = histogram([1, 1, 0]), histogram([0, 1, 1])
        r = compare_palette_entropy(a, b)
        self.assertEqual(r["jensen_shannon_divergence_bits"], .5)
        self.assertAlmostEqual(r["jensen_shannon_distance"], math.sqrt(.5), places=7)
        self.assertEqual(r["total_variation"], .5)
        self.assertEqual(r["jensen_shannon_distance"],
                         compare_palette_entropy(b, a)["jensen_shannon_distance"])

    def test_no_mutation(self):
        a, b = histogram([2, 1]), histogram([3, 4])
        before = copy.deepcopy((a, b))
        compare_palette_entropy(a, b)
        self.assertEqual((a, b), before)

    def test_invalid_count_total(self):
        a = histogram([2, 1])
        a["sample_pixels"] = 4
        with self.assertRaises(ValueError):
            palette_entropy(a)

    def test_local_images_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = (Path(directory) / name for name in ("a.png", "b.png"))
            Image.new("RGB", (8, 8), "red").save(a)
            Image.new("RGB", (8, 8), "blue").save(b)
            before = (a.read_bytes(), b.read_bytes())
            result = artwork_entropy_study(a, b)
            self.assertEqual(result["jensen_shannon_divergence_bits"], 1)
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([str(a), str(b)]), 0)
            self.assertEqual(json.loads(output.getvalue()), result)
            self.assertEqual((a.read_bytes(), b.read_bytes()), before)
