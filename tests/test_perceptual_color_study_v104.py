import io
import json
import math
import unittest
from contextlib import redirect_stdout

from klone.perceptual_color_study import _lab, color_study, main


class PerceptualColorStudyV104(unittest.TestCase):
    def test_black_white(self):
        for x in _lab((0, 0, 0)):
            self.assertAlmostEqual(x, 0, places=8)
        for actual, expected in zip(_lab((255, 255, 255)), (100, 0, 0)):
            self.assertAlmostEqual(actual, expected, places=3)

    def test_primary_references(self):
        for rgb, expected in (
            ((255, 0, 0), (53.2408, 80.0925, 67.2032)),
            ((0, 255, 0), (87.7347, -86.1827, 83.1793)),
            ((0, 0, 255), (32.2970, 79.1875, -107.8602)),
        ):
            for value, ref in zip(_lab(rgb), expected):
                self.assertAlmostEqual(value, ref, places=3)

    def test_gray_axis(self):
        for value in (1, 10, 11, 32, 128, 223):
            l, a, b = _lab((value,) * 3)
            self.assertGreater(l, 0)
            self.assertLess(l, 100)
            self.assertAlmostEqual(a, 0, places=3)
            self.assertAlmostEqual(b, 0, places=3)

    def test_equal_rgb_gray_distances(self):
        a, b = color_study()["observations"][:2]
        self.assertAlmostEqual(a["encoded_rgb_distance"], math.sqrt(3) * 32)
        self.assertEqual(a["encoded_rgb_distance"], b["encoded_rgb_distance"])
        self.assertGreater(a["delta_e_76"], b["delta_e_76"])

    def test_equal_rgb_channel_distances(self):
        rows = color_study()["observations"][2:]
        self.assertEqual([r["encoded_rgb_distance"] for r in rows], [32, 32, 32])
        self.assertEqual(len({round(r["delta_e_76"], 4) for r in rows}), 3)

    def test_distance_consistency(self):
        for r in color_study()["observations"]:
            self.assertGreater(r["delta_e_76"], 0)
            self.assertAlmostEqual(r["delta_e_76"],
                                   math.dist(r["first_lab_d65"], r["second_lab_d65"]))

    def test_cli_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), color_study())
        self.assertEqual(color_study(), color_study())
