"""Analytic and metamorphic checks for V10.6 synthetic compositions."""
import io
import json
import math
import unittest
from contextlib import redirect_stdout

from klone.spatial_composition_study import composition, spatial_study, main, PATTERNS


class SpatialCompositionStudyV106(unittest.TestCase):
    def test_centered_square(self):
        m = composition(PATTERNS[0][1])
        self.assertEqual(m["foreground_cells"], 16)
        self.assertEqual(m["foreground_fraction"], .25)
        self.assertEqual(m["negative_space_fraction"], .75)
        self.assertEqual(m["foreground_centroid_xy"], [3.5, 3.5])
        self.assertEqual(m["normalized_centroid_offset"], 0)
        self.assertEqual(m["foreground_bbox_xyxy_exclusive"], [2,2,6,6])
        self.assertEqual(m["left_right_agreement"], 1)
        self.assertEqual(m["top_bottom_agreement"], 1)
        self.assertEqual(m["rotation_180_agreement"], 1)
        self.assertEqual(m["internal_neighbor_edges"], 112)
        self.assertEqual(m["internal_transition_edges"], 16)
        self.assertEqual(m["foreground_component_sizes_4"], [16])

    def test_equal_area_different_placement(self):
        a, b = [composition(r) for _, r in PATTERNS[:2]]
        self.assertEqual(a["foreground_fraction"], b["foreground_fraction"])
        self.assertEqual(a["foreground_component_sizes_4"], b["foreground_component_sizes_4"])
        self.assertAlmostEqual(b["normalized_centroid_offset"], 4/7)
        self.assertEqual(b["left_right_agreement"], .5)
        self.assertEqual(b["internal_transition_edges"], 8)

    def test_equal_area_different_connectivity(self):
        a, b = [composition(r) for _, r in PATTERNS[2:4]]
        self.assertEqual(a["foreground_cells"], b["foreground_cells"])
        self.assertEqual(a["foreground_component_sizes_4"], [8,8])
        self.assertEqual(b["foreground_component_sizes_4"], [1]*16)
        self.assertGreater(b["internal_transition_edges"], a["internal_transition_edges"])

    def test_diagonal_not_four_connected(self):
        m = composition(PATTERNS[4][1])
        self.assertEqual(m["foreground_component_count_4"], 8)
        self.assertEqual(m["rotation_180_agreement"], 1)
        self.assertEqual(m["left_right_agreement"], .75)

    def test_empty_and_full(self):
        empty, full = [composition(r) for _, r in PATTERNS[-2:]]
        self.assertIsNone(empty["foreground_centroid_xy"])
        self.assertIsNone(empty["normalized_centroid_offset"])
        self.assertIsNone(empty["foreground_bbox_xyxy_exclusive"])
        self.assertEqual(empty["foreground_component_count_4"], 0)
        self.assertEqual(full["foreground_component_sizes_4"], [64])
        for m in (empty, full):
            self.assertEqual(m["left_right_agreement"], 1)
            self.assertEqual(m["internal_transition_fraction"], 0)

    def test_single_cell_and_rectangle(self):
        self.assertIsNone(composition(("1",))["internal_transition_fraction"])
        self.assertEqual(composition(("1",))["normalized_centroid_offset"], 0)
        m = composition(("100", "000"))
        self.assertEqual(m["internal_neighbor_edges"], 7)
        self.assertEqual(m["internal_transition_edges"], 2)
        self.assertEqual(m["normalized_centroid_offset"], 1)

    def test_reflection_invariance(self):
        for name, rows in PATTERNS:
            with self.subTest(name=name):
                a = composition(rows)
                b = composition(tuple(r[::-1] for r in rows))
                for key in ("foreground_fraction", "normalized_centroid_offset",
                            "internal_transition_fraction", "left_right_agreement",
                            "top_bottom_agreement", "rotation_180_agreement",
                            "foreground_component_sizes_4"):
                    if a[key] is None:
                        self.assertIsNone(b[key])
                    else:
                        self.assertEqual(a[key], b[key])

    def test_transpose_swaps_axes(self):
        rows = ("110", "001")
        a = composition(rows)
        b = composition(tuple("".join(col) for col in zip(*rows)))
        self.assertEqual(a["left_right_agreement"], b["top_bottom_agreement"])
        self.assertEqual(a["top_bottom_agreement"], b["left_right_agreement"])
        self.assertEqual(a["foreground_centroid_xy"][::-1], b["foreground_centroid_xy"])
        self.assertEqual(a["foreground_component_sizes_4"], b["foreground_component_sizes_4"])
        self.assertAlmostEqual(a["normalized_centroid_offset"], b["normalized_centroid_offset"])

    def test_accounting(self):
        for name, rows in PATTERNS:
            with self.subTest(name=name):
                m = composition(rows)
                self.assertEqual(sum(m["foreground_component_sizes_4"]), m["foreground_cells"])
                self.assertEqual(m["foreground_fraction"]+m["negative_space_fraction"], 1)
                self.assertLessEqual(m["internal_transition_edges"], m["internal_neighbor_edges"])
                for key in ("left_right_agreement", "top_bottom_agreement",
                            "rotation_180_agreement", "internal_transition_fraction"):
                    self.assertTrue(0 <= m[key] <= 1)

    def test_invalid_rasters(self):
        for rows in ((), ("",), ("10","1"), ("1x",)):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                composition(rows)

    def test_cli_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), spatial_study())
        self.assertEqual(spatial_study(), spatial_study())
