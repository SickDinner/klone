import base64
import io
import json
import unittest
from contextlib import redirect_stdout
from itertools import product

from PIL import Image
from klone.mathematical_symmetry import (
    NAMES, compose, transform_point, symmetry_study, render_symmetry_html, main,
)


class MathematicalSymmetryV92(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = symmetry_study()

    def test_eight_distinct_permutations(self):
        signatures = {
            tuple(transform_point(x, y, name, 3) for x, y in product(range(3), repeat=2))
            for name in NAMES
        }
        self.assertEqual(len(signatures), 8)
        self.assertTrue(all(len(set(s)) == 9 for s in signatures))

    def test_identity_and_inverses(self):
        for name in NAMES:
            self.assertEqual(compose(name, "identity"), name)
            self.assertEqual(compose("identity", name), name)
            inverse = next(row["inverse"] for row in self.report["observations"]
                           if row["operation"] == name)
            self.assertEqual(compose(name, inverse), "identity")
            self.assertEqual(compose(inverse, name), "identity")

    def test_associativity(self):
        for a, b, c in product(NAMES, repeat=3):
            self.assertEqual(compose(compose(a, b), c), compose(a, compose(b, c)))

    def test_noncommutative(self):
        self.assertNotEqual(compose("mirror", "rotate90"), compose("rotate90", "mirror"))

    def test_known_transform(self):
        self.assertEqual(transform_point(0, 0, "rotate90", 5), (4, 0))
        self.assertEqual(transform_point(0, 0, "mirror", 5), (4, 0))
        self.assertEqual(compose("rotate90", "rotate270"), "identity")

    def test_invalid_parameters(self):
        for args in ((0, 0, "bad", 5), (-1, 0, "identity", 5),
                     (0, 5, "identity", 5), (0, 0, "identity", 1)):
            with self.assertRaises(ValueError):
                transform_point(*args)

    def test_palette_and_png(self):
        rows = self.report["observations"]
        self.assertEqual(rows[0]["changed_pixels"], 0)
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertTrue(row["color_counts_preserved"])
            with Image.open(io.BytesIO(base64.b64decode(row["preview_png_base64"]))) as im:
                self.assertEqual((im.format, im.size), ("PNG", (48, 48)))

    def test_html_offline(self):
        html = render_symmetry_html(self.report)
        self.assertEqual(html.count("data:image/png;base64,"), 8)
        self.assertIn("Composition: row first, column second", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("https://", html)

    def test_cli_and_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
        self.assertEqual(symmetry_study(), self.report)
