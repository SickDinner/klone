import io
import json
import math
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

from klone.nature_mathematics import (
    fibonacci_sequence, phyllotaxis_study, render_phyllotaxis_svg, main,
)


class NatureMathematicsV87(unittest.TestCase):
    def test_fibonacci_known_terms(self):
        self.assertEqual(fibonacci_sequence(12),
                         [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89])

    def test_fibonacci_recurrence(self):
        terms = fibonacci_sequence(32)
        self.assertTrue(all(c == a + b for a, b, c in zip(terms, terms[1:], terms[2:])))

    def test_golden_ratio_and_angle(self):
        r = phyllotaxis_study(72)
        phi = r["golden_ratio"]
        self.assertAlmostEqual(phi**2, phi + 1)
        self.assertAlmostEqual(r["golden_angle_degrees"], 137.50776405003785)

    def test_count_and_radial_spacing(self):
        r = phyllotaxis_study(144)
        self.assertEqual(len(r["points"]), 144)
        for n, p in enumerate(r["points"]):
            self.assertEqual(p["index"], n)
            self.assertAlmostEqual(p["x"]**2 + p["y"]**2, n / 143, places=8)
        self.assertEqual(r["points"][-1]["radius"], 1)

    def test_angle_between_nonzero_points(self):
        r = phyllotaxis_study(72)
        p, q = r["points"][1:3]
        difference = (math.degrees(math.atan2(q["y"], q["x"]) -
                                  math.atan2(p["y"], p["x"]))) % 360
        self.assertAlmostEqual(difference, r["golden_angle_degrees"], places=6)

    def test_single_point(self):
        self.assertEqual(phyllotaxis_study(1)["points"],
                         [{"index": 0, "radius": 0, "x": 0, "y": 0}])

    def test_invalid_bounds(self):
        for fn, values in ((fibonacci_sequence, (0, 33, True, 1.0)),
                           (phyllotaxis_study, (0, 513, True, 1.0))):
            for value in values:
                with self.assertRaises(ValueError):
                    fn(value)

    def test_svg(self):
        root = ET.fromstring(render_phyllotaxis_svg(144))
        self.assertEqual(len(root.findall("{http://www.w3.org/2000/svg}circle")), 144)

    def test_cli_and_repeatability(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--count", "72"]), 0)
        self.assertEqual(json.loads(output.getvalue()), phyllotaxis_study(72))
        self.assertEqual(phyllotaxis_study(512), phyllotaxis_study(512))
