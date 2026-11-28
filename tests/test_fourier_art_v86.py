import io
import json
import math
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

from klone.fourier_art import fourier_study, render_fourier_svg, main


class FourierArtV86(unittest.TestCase):
    def test_first_harmonic(self):
        r = fourier_study(1)
        self.assertAlmostEqual(r["harmonics"][0]["amplitude"], 4 / math.pi)
        self.assertAlmostEqual(r["points"][180][1], 4 / math.pi, places=9)

    def test_odd_harmonics(self):
        r = fourier_study(9)
        self.assertEqual([h["order"] for h in r["harmonics"]], list(range(1, 18, 2)))

    def test_parseval_first_term(self):
        r = fourier_study(1)
        self.assertAlmostEqual(r["theoretical_residual_mean_square"], 1 - 8 / math.pi**2)

    def test_residual_decreases(self):
        residuals = [fourier_study(n)["theoretical_residual_mean_square"]
                     for n in (1, 4, 9, 16, 32)]
        self.assertTrue(all(a > b > 0 for a, b in zip(residuals, residuals[1:])))

    def test_period_and_half_wave_symmetry(self):
        points = fourier_study(16)["points"]
        self.assertEqual(len(points), 721)
        self.assertEqual(points[0][1], points[-1][1])
        for i in range(361):
            self.assertAlmostEqual(points[i][1], -points[i + 360][1], places=9)

    def test_gibbs_overshoot(self):
        peak = fourier_study(16)["sampled_peak_absolute"]
        self.assertTrue(1.16 < peak < 1.20)

    def test_invalid_terms(self):
        for value in (0, 33, True, 9.0, "9"):
            with self.assertRaises(ValueError):
                fourier_study(value)

    def test_svg(self):
        root = ET.fromstring(render_fourier_svg(9))
        line = root.find("{http://www.w3.org/2000/svg}polyline")
        self.assertEqual(len(line.attrib["points"].split()), 721)

    def test_cli_json_and_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--terms", "9"]), 0)
        self.assertEqual(json.loads(out.getvalue()), fourier_study(9))
