import io
import json
import math
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

from klone.harmonic_geometry import harmonic_study, render_harmonic_svg, main


class HarmonicGeometryV84(unittest.TestCase):
    def test_octave(self):
        self.assertEqual(harmonic_study(1, 2)["interval_y_over_x_cents"], 1200)

    def test_fifth(self):
        self.assertAlmostEqual(harmonic_study(2, 3)["interval_y_over_x_cents"],
                               701.95500087, places=7)

    def test_ratio_reduction(self):
        a, b = harmonic_study(4, 6), harmonic_study(2, 3)
        self.assertEqual(a["reduced_ratio_xy"], [2, 3])
        self.assertEqual(a["points"], b["points"])

    def test_circle_at_quadrature(self):
        r = harmonic_study(1, 1, 1)
        for x, y in r["points"]:
            self.assertAlmostEqual(x*x + y*y, 1, places=8)

    def test_line_in_phase(self):
        self.assertTrue(all(x == y for x, y in harmonic_study(1, 1, 0)["points"]))

    def test_closed_and_bounded(self):
        for a, b in ((2, 3), (5, 7), (12, 11)):
            points = harmonic_study(a, b)["points"]
            self.assertEqual(len(points), 721)
            self.assertEqual(points[0], points[-1])
            self.assertTrue(all(-1 <= v <= 1 for point in points for v in point))

    def test_invalid_parameters(self):
        for args in ((0, 1), (1, 13), (True, 1), (1, 2, 4), (1, 2, 1.0)):
            with self.assertRaises(ValueError):
                harmonic_study(*args)

    def test_svg(self):
        root = ET.fromstring(render_harmonic_svg(2, 3))
        line = root.find("{http://www.w3.org/2000/svg}polyline")
        self.assertEqual(len(line.attrib["points"].split()), 721)

    def test_cli_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--x-ratio", "3", "--y-ratio", "4"]), 0)
        self.assertEqual(json.loads(out.getvalue()), harmonic_study(3, 4))
