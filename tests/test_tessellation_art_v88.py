import io
import json
import math
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

from klone.tessellation_art import tessellation_study, render_tessellation_svg, main


class TessellationArtV88(unittest.TestCase):
    def test_triangle(self):
        report = tessellation_study("triangle")
        self.assertEqual(report["sides_per_tile"], 3)
        self.assertEqual(report["interior_angle_degrees"], 60)
        self.assertEqual(report["tiles_per_vertex"], 6)
        self.assertAlmostEqual(report["unit_tile_area"], math.sqrt(3) / 4)

    def test_square(self):
        report = tessellation_study("square")
        self.assertEqual(report["sides_per_tile"], 4)
        self.assertEqual(report["interior_angle_degrees"], 90)
        self.assertEqual(report["tiles_per_vertex"], 4)
        self.assertAlmostEqual(report["unit_tile_area"], 1)

    def test_hexagon(self):
        report = tessellation_study("hexagon")
        self.assertEqual(report["sides_per_tile"], 6)
        self.assertEqual(report["interior_angle_degrees"], 120)
        self.assertEqual(report["tiles_per_vertex"], 3)
        self.assertAlmostEqual(report["unit_tile_area"], 3 * math.sqrt(3) / 2)

    def test_full_vertex_angle(self):
        for kind in ("triangle", "square", "hexagon"):
            r = tessellation_study(kind)
            self.assertEqual(r["tiles_per_vertex"] * r["interior_angle_degrees"], 360)
            self.assertEqual(r["unit_tile_perimeter"], r["sides_per_tile"])

    def test_invalid_kind(self):
        for kind in ("pentagon", "", None, [], True):
            with self.assertRaises(ValueError):
                tessellation_study(kind)

    def test_svg_polygons(self):
        ns = "{http://www.w3.org/2000/svg}"
        for kind, sides in (("triangle", 3), ("square", 4), ("hexagon", 6)):
            root = ET.fromstring(render_tessellation_svg(kind))
            self.assertEqual(root.attrib["viewBox"], "0 0 360 360")
            polygons = root.findall(ns + "polygon")
            self.assertGreater(len(polygons), 10)
            for polygon in polygons:
                points = [tuple(map(float, p.split(",")))
                          for p in polygon.attrib["points"].split()]
                self.assertEqual(len(points), sides)
                for p, q in zip(points, points[1:] + points[:1]):
                    self.assertAlmostEqual(math.dist(p, q), 32, places=5)

    def test_svg_repeatability(self):
        for kind in ("triangle", "square", "hexagon"):
            self.assertEqual(render_tessellation_svg(kind), render_tessellation_svg(kind))
            self.assertNotIn("<script", render_tessellation_svg(kind))

    def test_cli_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--kind", "hexagon"]), 0)
        self.assertEqual(json.loads(out.getvalue()), tessellation_study("hexagon"))

    def test_cli_svg(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--kind", "triangle", "--format", "svg"]), 0)
        self.assertEqual(out.getvalue().strip(), render_tessellation_svg("triangle"))
