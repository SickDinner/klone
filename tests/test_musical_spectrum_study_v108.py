"""Analytic and metamorphic checks for synthetic musical spectra."""
import io
import json
import math
import unittest
from contextlib import redirect_stdout

from klone.musical_spectrum_study import FIXTURES, mel_coordinate, spectrum_metrics, spectrum_study, main


class MusicalSpectrumStudyV108(unittest.TestCase):
    def test_pure_tone(self):
        m = spectrum_metrics(220, (1,))
        self.assertEqual(m["power_centroid_hz"], 220)
        self.assertEqual(m["power_spread_hz"], 0)
        self.assertEqual(m["harmonic_power_entropy_bits"], 0)
        self.assertEqual(m["power_rolloff_85_hz"], 220)
        self.assertAlmostEqual(m["ideal_cycle_rms"], 1/math.sqrt(2))

    def test_two_equal_harmonics(self):
        m = spectrum_metrics(220, (1,1))
        self.assertEqual(m["power_centroid_hz"], 330)
        self.assertEqual(m["power_spread_hz"], 110)
        self.assertEqual(m["harmonic_power_entropy_bits"], 1)
        self.assertEqual(m["fundamental_power_fraction"], .5)
        self.assertEqual(m["power_rolloff_85_hz"], 440)

    def test_soft_harmonics(self):
        m = spectrum_metrics(220, (1,.5,.25,.125))
        self.assertAlmostEqual(m["total_relative_power"], 85/64)
        self.assertAlmostEqual(m["power_centroid_hz"], 220*112/85)
        self.assertAlmostEqual(m["fundamental_power_fraction"], 64/85)
        self.assertEqual(m["power_rolloff_85_hz"], 440)

    def test_equal_four_harmonics(self):
        m = spectrum_metrics(220, (1,1,1,1))
        self.assertEqual(m["power_centroid_hz"], 550)
        self.assertEqual(m["harmonic_power_entropy_bits"], 2)
        self.assertEqual(m["power_rolloff_85_hz"], 880)
        self.assertEqual(m["normalized_harmonic_power"], [.25]*4)

    def test_level_scaling(self):
        a = spectrum_metrics(220, (1,.5,.25,.125))
        b = spectrum_metrics(220, (.25,.125,.0625,.03125))
        for key in ("normalized_harmonic_power", "power_centroid_hz", "power_spread_hz",
                    "power_centroid_mel", "harmonic_power_entropy_bits",
                    "power_rolloff_85_hz", "fundamental_power_fraction"):
            self.assertEqual(a[key], b[key], key)
        self.assertAlmostEqual(b["total_relative_power"], a["total_relative_power"]/16)
        self.assertAlmostEqual(b["ideal_cycle_rms"], a["ideal_cycle_rms"]/4)

    def test_octave_scaling(self):
        a = spectrum_metrics(220, (1,.5,.25,.125))
        b = spectrum_metrics(440, (1,.5,.25,.125))
        for key in ("power_centroid_hz", "power_spread_hz", "power_rolloff_85_hz"):
            self.assertAlmostEqual(b[key], 2*a[key])
        self.assertEqual(a["harmonic_power_entropy_bits"], b["harmonic_power_entropy_bits"])
        self.assertGreater(b["power_centroid_mel"], a["power_centroid_mel"])
        self.assertLess(b["power_centroid_mel"], 2*a["power_centroid_mel"])

    def test_mel_coordinate(self):
        self.assertEqual(mel_coordinate(0), 0)
        self.assertAlmostEqual(mel_coordinate(1000), 999.985537, places=4)
        self.assertGreater(mel_coordinate(440), mel_coordinate(220))
        for bad in (-1,float("inf"),float("nan")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mel_coordinate(bad)

    def test_missing_fundamental_and_silence(self):
        m = spectrum_metrics(220, (0,1))
        self.assertEqual(m["power_centroid_hz"], 440)
        self.assertEqual(m["fundamental_power_fraction"], 0)
        self.assertEqual(m["active_harmonic_count"], 1)
        s = spectrum_metrics(220, (0,0))
        self.assertEqual(s["total_relative_power"], 0)
        self.assertEqual(s["ideal_cycle_rms"], 0)
        for key in ("power_centroid_hz", "power_spread_hz", "power_centroid_mel",
                    "harmonic_power_entropy_bits", "power_rolloff_85_hz",
                    "normalized_harmonic_power", "fundamental_power_fraction"):
            self.assertIsNone(s[key])

    def test_accounting(self):
        for name,f,a in FIXTURES:
            with self.subTest(name=name):
                m = spectrum_metrics(f,a)
                self.assertAlmostEqual(m["ideal_cycle_rms"]**2, m["total_relative_power"]/2)
                if m["total_relative_power"]:
                    self.assertAlmostEqual(sum(m["normalized_harmonic_power"]), 1)
                    self.assertGreaterEqual(m["power_centroid_hz"], f)
                    self.assertLessEqual(m["power_centroid_hz"], f*len(a))
                    self.assertGreaterEqual(m["harmonic_power_entropy_bits"], 0)

    def test_invalid_input(self):
        for f,a in ((0,(1,)), (float("nan"),(1,)), (1001,(1,)), (220,()),
                    (220,(-1,)), (220,(float("inf"),)), (220,(1.01,)),
                    (220,(1,)*17)):
            with self.subTest(f=f,a=a), self.assertRaises(ValueError):
                spectrum_metrics(f,a)

    def test_cli_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), spectrum_study())
        self.assertEqual(spectrum_study(), spectrum_study())
