"""Numerical reference and deterministic CLI tests for V10.5."""
import io
import json
import math
import unittest
from contextlib import redirect_stdout

from klone.advanced_color_study import advanced_color_study, delta_e_2000, main, oklab
from klone.perceptual_color_study import color_study

# Sharma, Wu, Dalal supplementary numerical reference data:
# https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/dataNprograms/ciede2000testdata.txt
REFERENCE = """
50 2.6772 -79.7751 50 0 -82.7485 2.0425
50 3.1571 -77.2803 50 0 -82.7485 2.8615
50 2.8361 -74.0200 50 0 -82.7485 3.4412
50 -1.3802 -84.2814 50 0 -82.7485 1.0000
50 -1.1848 -84.8006 50 0 -82.7485 1.0000
50 -0.9009 -85.5211 50 0 -82.7485 1.0000
50 0 0 50 -1 2 2.3669
50 -1 2 50 0 0 2.3669
50 2.49 -0.001 50 -2.49 0.0009 7.1792
50 2.49 -0.001 50 -2.49 0.0010 7.1792
50 2.49 -0.001 50 -2.49 0.0011 7.2195
50 2.49 -0.001 50 -2.49 0.0012 7.2195
50 -0.001 2.49 50 0.0009 -2.49 4.8045
50 -0.001 2.49 50 0.0010 -2.49 4.8045
50 -0.001 2.49 50 0.0011 -2.49 4.7461
50 2.5 0 50 0 -2.5 4.3065
50 2.5 0 73 25 -18 27.1492
50 2.5 0 61 -5 29 22.8977
50 2.5 0 56 -27 -3 31.9030
50 2.5 0 58 24 15 19.4535
50 2.5 0 50 3.1736 0.5854 1.0000
50 2.5 0 50 3.2972 0 1.0000
50 2.5 0 50 1.8634 0.5757 1.0000
50 2.5 0 50 3.2592 0.3350 1.0000
60.2574 -34.0099 36.2677 60.4626 -34.1751 39.4387 1.2644
63.0109 -31.0961 -5.8663 62.8187 -29.7946 -4.0864 1.2630
61.2901 3.7196 -5.3901 61.4292 2.2480 -4.9620 1.8731
35.0831 -44.1164 3.7933 35.0232 -40.0716 1.5901 1.8645
22.7233 20.0904 -46.6940 23.0331 14.9730 -42.5619 2.0373
36.4612 47.8580 18.3852 36.2715 50.5065 21.2231 1.4146
90.8027 -2.0831 1.4410 91.1528 -1.6435 0.0447 1.4441
90.9257 -0.5406 -0.9208 88.6381 -0.8985 -0.7239 1.5381
6.7747 -0.2908 -2.4247 5.8714 -0.0985 -2.2286 0.6377
2.0776 0.0795 -1.1350 0.9033 -0.0636 -0.5514 0.9082
""".strip()


class AdvancedColorStudyV105(unittest.TestCase):
    def test_reference_dataset(self):
        lines = REFERENCE.splitlines()
        self.assertEqual(len(lines), 34)
        for i, line in enumerate(lines, 1):
            row = tuple(map(float, line.split()))
            with self.subTest(row=i):
                self.assertAlmostEqual(delta_e_2000(row[:3], row[3:6]),
                                       row[6], delta=0.00005)

    def test_reference_symmetry(self):
        for i, line in enumerate(REFERENCE.splitlines(), 1):
            row = tuple(map(float, line.split()))
            with self.subTest(row=i):
                self.assertAlmostEqual(delta_e_2000(row[:3], row[3:6]),
                                       delta_e_2000(row[3:6], row[:3]), places=10)

    def test_identity_and_neutral(self):
        for lab in ((0, 0, 0), (50, 20, -40), (100, 0, 0)):
            self.assertEqual(delta_e_2000(lab, lab), 0)
        self.assertAlmostEqual(delta_e_2000((0, 0, 0), (100, 0, 0)), 100)

    def test_nonfinite_rejected(self):
        for bad in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError):
                delta_e_2000((bad, 0, 0), (50, 0, 0))

    def test_oklab_primaries(self):
        # Reference rounded to six decimals.
        for rgb, expected in (
            ((255, 0, 0), (0.627955, 0.224863, 0.125846)),
            ((0, 255, 0), (0.866440, -0.233888, 0.179498)),
            ((0, 0, 255), (0.452014, -0.032457, -0.311528)),
            ((0, 0, 0), (0, 0, 0)),
            ((255, 255, 255), (1, 0, 0)),
        ):
            with self.subTest(rgb=rgb):
                for actual, ref in zip(oklab(rgb), expected):
                    self.assertAlmostEqual(actual, ref, delta=0.000001)

    def test_oklab_gray_axis(self):
        previous = -1
        for value in (0, 1, 10, 11, 32, 128, 223, 255):
            l, a, b = oklab((value,) * 3)
            self.assertGreater(l, previous)
            self.assertAlmostEqual(a, 0, places=6)
            self.assertAlmostEqual(b, 0, places=6)
            previous = l

    def test_v104_compatibility(self):
        old = color_study()["observations"]
        new = advanced_color_study()["observations"]
        self.assertEqual(len(old), len(new))
        for previous, current in zip(old, new):
            self.assertEqual(previous, {k: current[k] for k in previous})
            self.assertGreater(current["delta_e_2000"], 0)
            self.assertAlmostEqual(current["oklab_distance"],
                                   math.dist(current["first_oklab"],
                                             current["second_oklab"]))

    def test_rankings_and_cli(self):
        study = advanced_color_study()
        for key, names in study["descending_order_by_model"].items():
            expected = sorted(study["observations"],
                              key=lambda r: (-r[key], r["example"]))
            self.assertEqual(names, [r["example"] for r in expected])
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(output.getvalue()), study)
        self.assertEqual(advanced_color_study(), study)
