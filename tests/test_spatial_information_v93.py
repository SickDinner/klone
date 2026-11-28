import io
import json
import math
import unittest
from contextlib import redirect_stdout

from klone.spatial_information import spatial_information_study, main


class SpatialInformationV93(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = spatial_information_study()
        cls.rows = {r["pattern"]: r for r in cls.report["observations"]}

    def test_inventory(self):
        self.assertEqual(self.report["dimensions"], [32, 32])
        self.assertEqual(len(self.rows), 5)

    def test_pixel_entropy(self):
        for name, row in self.rows.items():
            self.assertEqual(row["pixel_entropy_bits"], 0 if name == "constant" else 1)

    def test_constant(self):
        for direction in ("horizontal", "vertical"):
            s = self.rows["constant"][direction]
            self.assertEqual(s["joint_counts"], {"00": 992, "01": 0, "10": 0, "11": 0})
            self.assertEqual(s["mutual_information_bits"], 0)
            self.assertEqual(s["conditional_second_given_first_bits"], 0)

    def test_checkerboard(self):
        for direction in ("horizontal", "vertical"):
            s = self.rows["checkerboard"][direction]
            self.assertEqual(s["joint_counts"], {"00": 0, "01": 496, "10": 496, "11": 0})
            self.assertEqual(s["mutual_information_bits"], 1)
            self.assertEqual(s["conditional_second_given_first_bits"], 0)

    def test_vertical_stripes(self):
        row = self.rows["vertical_stripes"]
        self.assertEqual(row["horizontal"]["joint_counts"], self.rows["checkerboard"]["horizontal"]["joint_counts"])
        self.assertEqual(row["vertical"]["joint_counts"], {"00": 496, "01": 0, "10": 0, "11": 496})
        self.assertEqual(row["vertical"]["mutual_information_bits"], 1)

    def test_split_direction(self):
        a, b = self.rows["vertical_split"], self.rows["horizontal_split"]
        self.assertEqual(a["horizontal"], b["vertical"])
        self.assertEqual(a["vertical"], b["horizontal"])
        self.assertEqual(a["horizontal"]["joint_counts"], {"00": 480, "01": 32, "10": 0, "11": 480})
        self.assertGreater(a["horizontal"]["conditional_second_given_first_bits"], 0)

    def test_information_identities(self):
        for row in self.rows.values():
            for d in ("horizontal", "vertical"):
                s = row[d]
                self.assertEqual(s["pair_count"], 992)
                self.assertEqual(sum(s["joint_counts"].values()), 992)
                self.assertAlmostEqual(s["joint_entropy_bits"],
                                       s["first_entropy_bits"] + s["conditional_second_given_first_bits"])
                self.assertAlmostEqual(s["second_entropy_bits"],
                                       s["mutual_information_bits"] + s["conditional_second_given_first_bits"])
                self.assertTrue(0 <= s["mutual_information_bits"] <= 1 + 1e-12)

    def test_cli_and_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
        self.assertEqual(spatial_information_study(), self.report)
