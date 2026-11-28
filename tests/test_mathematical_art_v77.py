import json
import math
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from io import StringIO

from klone.mathematical_art import polygon_study, render_polygon, main


class MathematicalArtV77(unittest.TestCase):
    def test_square(self):
        r = polygon_study(4)
        self.assertAlmostEqual(r["area"], 2)
        self.assertAlmostEqual(r["perimeter"], 4 * math.sqrt(2))
        self.assertEqual(r["interior_angle_degrees"], 90)

    def test_triangle(self):
        r = polygon_study(3)
        self.assertAlmostEqual(r["area"], 3 * math.sqrt(3) / 4)
        self.assertEqual(r["reflection_axes"], 3)

    def test_72(self):
        r = polygon_study(72)
        self.assertEqual(r["central_angle_degrees"], 5)
        self.assertEqual(r["interior_angle_degrees"], 175)
        self.assertEqual(r["rotation_order"], 72)
        self.assertEqual(len(r["vertices"]), 72)

    def test_unit_radius(self):
        for x, y in polygon_study(72)["vertices"]:
            self.assertAlmostEqual(math.hypot(x, y), 1, places=9)

    def test_area_approaches_circle(self):
        self.assertLess(polygon_study(6)["area"], polygon_study(72)["area"])
        self.assertLess(polygon_study(72)["area"], math.pi)

    def test_invalid_bounds(self):
        for value in (True, 2, 73, 4.0, "4"):
            with self.assertRaises(ValueError):
                polygon_study(value)

    def test_svg_structure(self):
        root = ET.fromstring(render_polygon(72))
        self.assertTrue(root.tag.endswith("svg"))
        polygon = root.find("{http://www.w3.org/2000/svg}polygon")
        self.assertEqual(len(polygon.attrib["points"].split()), 72)

    def test_cli_json(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--sides", "8"]), 0)
        self.assertEqual(json.loads(output.getvalue()), polygon_study(8))
