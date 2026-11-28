import io
import json
import unittest
from contextlib import redirect_stdout

from klone.algorithmic_aesthetics import aesthetics_study, main


class AlgorithmicAestheticsV94(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = aesthetics_study()
        cls.metrics = {r["metric"]: r for r in cls.report["comparisons"]}

    def test_inventory(self):
        self.assertEqual(self.report["schema"], "klone.algorithmic_aesthetics.v1")
        self.assertEqual(self.report["dimensions"], [32, 32])
        self.assertEqual(len(self.report["profiles"]), 5)
        self.assertEqual(len(self.metrics), 4)

    def test_pair_accounting(self):
        for row in self.metrics.values():
            self.assertEqual(row["total_pair_count"], 10)
            self.assertEqual(row["matching_pair_count"], len(row["matching_pairs"]))
            self.assertEqual(row["matching_pair_count"] + row["distinct_pair_count"], 10)

    def test_entropy_collisions(self):
        self.assertEqual(self.metrics["pixel_entropy"]["matching_pair_count"], 6)

    def test_conditional_entropy_collisions(self):
        pairs = self.metrics["conditional_entropy"]["matching_pairs"]
        self.assertEqual(len(pairs), 3)
        self.assertIn(["checkerboard", "vertical_stripes"], pairs)
        self.assertIn(["checkerboard", "constant"], pairs)
        self.assertIn(["vertical_stripes", "constant"], pairs)

    def test_mutual_information_distinguishes_fixtures(self):
        self.assertEqual(self.metrics["mutual_information"]["matching_pair_count"], 0)

    def test_ordered_pair_counts_distinguish_fixtures(self):
        self.assertEqual(self.metrics["directional_pair_counts"]["matching_pair_count"], 0)

    def test_cli_and_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
        self.assertEqual(aesthetics_study(), self.report)
