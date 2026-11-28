"""Alternative mathematical reference checks for educational creative fixtures.

These tests use separately formulated calculations, not independent reviewers
or an external scientific validation dataset.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
import math
import unittest

from klone.spatial_information import spatial_information_study
from klone.musical_mathematics import tuning_study
from klone.mathematical_rhythm import rhythm_study


class CreativeResearchValidationV99(unittest.TestCase):
    def test_direct_mutual_information(self):
        for row in spatial_information_study()["observations"]:
            for direction in ("horizontal", "vertical"):
                s = row[direction]
                c = s["joint_counts"]
                n = sum(c.values())
                expected = sum(
                    c[a+b] / n * math.log2(
                        c[a+b] * n /
                        ((c[a+"0"] + c[a+"1"]) * (c["0"+b] + c["1"+b])))
                    for a, b in product("01", repeat=2) if c[a+b]
                )
                self.assertAlmostEqual(s["mutual_information_bits"], expected, places=12)

    def test_direct_conditional_entropy(self):
        for row in spatial_information_study()["observations"]:
            for direction in ("horizontal", "vertical"):
                s = row[direction]
                c = s["joint_counts"]
                n = sum(c.values())
                expected = -sum(
                    c[a+b] / n * math.log2(c[a+b] / (c[a+"0"] + c[a+"1"]))
                    for a, b in product("01", repeat=2) if c[a+b]
                )
                self.assertAlmostEqual(s["conditional_second_given_first_bits"],
                                       expected, places=12)

    def test_analytic_joint_count_reference(self):
        split = {"00": 480, "01": 32, "10": 0, "11": 480}
        same = {"00": 496, "01": 0, "10": 0, "11": 496}
        alternate = {"00": 0, "01": 496, "10": 496, "11": 0}
        stripe = {"00": 0, "01": 512, "10": 480, "11": 0}
        constant = {"00": 992, "01": 0, "10": 0, "11": 0}
        expected = {
            "vertical_split": (split, same),
            "horizontal_split": (same, split),
            "checkerboard": (alternate, alternate),
            "vertical_stripes": (stripe, same),
            "constant": (constant, constant),
        }
        rows = spatial_information_study()["observations"]
        self.assertEqual({r["pattern"] for r in rows}, set(expected))
        for r in rows:
            self.assertEqual((r["horizontal"]["joint_counts"], r["vertical"]["joint_counts"]),
                             expected[r["pattern"]])

    def test_decimal_tuning_reference(self):
        with localcontext() as ctx:
            ctx.prec = 50
            ln2 = Decimal(2).ln()
            for r in tuning_study()["intervals"]:
                f = Fraction(r["just_ratio"])
                ratio = Decimal(f.numerator) / Decimal(f.denominator)
                equal = (ln2 * Decimal(r["semitones"]) / Decimal(12)).exp()
                cents = Decimal(1200) * (ratio / equal).ln() / ln2
                self.assertAlmostEqual(r["just_frequency_hz"], float(440 * ratio), places=10)
                self.assertAlmostEqual(r["equal_frequency_hz"], float(440 * equal), places=10)
                self.assertAlmostEqual(r["just_minus_equal_cents"], float(cents), places=10)

    def test_rhythm_positions_ceil_reference(self):
        # The kth pulse occurs on the last step before ceil(k*n/p).
        for steps in range(1, 73):
            for pulses in range(steps + 1):
                expected = [math.ceil(Fraction(k * steps, pulses)) - 1
                            for k in range(1, pulses + 1)]
                report = rhythm_study(steps, pulses)
                self.assertEqual(report["pulse_positions_zero_based"], expected)

    def test_rhythm_period_gcd_reference(self):
        for steps in range(1, 73):
            for pulses in range(steps + 1):
                divisor = math.gcd(steps, pulses)
                report = rhythm_study(steps, pulses)
                self.assertEqual(report["fundamental_period_steps"], steps // divisor)
                self.assertEqual(report["rotational_repetitions"], divisor)
