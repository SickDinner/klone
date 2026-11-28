import io
import json
import math
import unittest
from contextlib import redirect_stdout

from klone.musical_mathematics import tuning_study, main


class MusicalMathematicsV96(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tuning_study()
        cls.rows = {r["interval"]: r for r in cls.report["intervals"]}

    def test_inventory(self):
        self.assertEqual(self.report["reference_hz"], 440)
        self.assertEqual(len(self.rows), 8)

    def test_unison_and_octave(self):
        for name, hz in (("unison", 440), ("octave", 880)):
            row = self.rows[name]
            self.assertEqual(row["just_frequency_hz"], hz)
            self.assertEqual(row["equal_frequency_hz"], hz)
            self.assertEqual(row["just_minus_equal_cents"], 0)

    def test_pure_fifth(self):
        r = self.rows["perfect_fifth"]
        self.assertEqual(r["just_frequency_hz"], 660)
        self.assertAlmostEqual(r["just_minus_equal_cents"], 1.9550008654)

    def test_major_third(self):
        r = self.rows["major_third"]
        self.assertEqual(r["just_frequency_hz"], 550)
        self.assertAlmostEqual(r["just_minus_equal_cents"], -13.6862861352)

    def test_minor_third(self):
        r = self.rows["minor_third"]
        self.assertEqual(r["just_frequency_hz"], 528)
        self.assertAlmostEqual(r["just_minus_equal_cents"], 15.6412870006)

    def test_frequency_cents_consistency(self):
        for r in self.rows.values():
            self.assertAlmostEqual(
                1200 * math.log2(r["just_frequency_hz"] / r["equal_frequency_hz"]),
                r["just_minus_equal_cents"])
            self.assertEqual(r["equal_cents"], 100 * r["semitones"])

    def test_pythagorean_comma(self):
        comma = self.report["pythagorean_comma"]
        self.assertEqual(comma["ratio"], "531441/524288")
        self.assertAlmostEqual(comma["cents"], 23.4600103846)

    def test_cli_and_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
        self.assertEqual(tuning_study(), self.report)
