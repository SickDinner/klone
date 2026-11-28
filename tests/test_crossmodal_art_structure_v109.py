"""Analytic tests for cross-domain structural descriptors."""
import io
import json
import unittest
from collections import Counter
from contextlib import redirect_stdout

from klone.crossmodal_art_structure import profiles, compare, crossmodal_study, main


class CrossmodalArtStructureV109(unittest.TestCase):
    def setUp(self):
        self.rows = {(r["domain"],r["example"]):r for r in profiles()}

    def test_inventory(self):
        self.assertEqual(len(self.rows), 25)
        self.assertEqual(Counter(d for d,n in self.rows),
                         {"spatial":7,"rhythm":9,"spectrum":9})

    def test_equal_occupancy_not_equal_structure(self):
        a = self.rows["spatial","centered_square"]
        b = self.rows["rhythm","regular_quarters"]
        c = compare(a,b)
        self.assertEqual(c["exact_descriptor_matches"],
                         ["binary_occupancy_fraction","binary_occupancy_entropy_bits"])
        self.assertAlmostEqual(c["absolute_descriptor_differences"]["local_transition_fraction"],
                               .5-16/112)

    def test_exact_abstract_descriptor_match(self):
        a = self.rows["spatial","checker_sparse"]
        b = self.rows["rhythm","regular_quarters"]
        self.assertEqual(len(compare(a,b)["exact_descriptor_matches"]), 3)

    def test_missing_not_zero(self):
        a = self.rows["spatial","empty"]
        b = self.rows["spectrum","silence"]
        c = compare(a,b)
        self.assertEqual(c["undefined_descriptors"], ["local_transition_fraction"])
        self.assertIsNone(c["absolute_descriptor_differences"]["local_transition_fraction"])
        self.assertEqual(len(c["exact_descriptor_matches"]), 2)

    def test_spectrum_occupancy_not_power_entropy(self):
        a = self.rows["spectrum","soft_harmonics"]["features"]
        b = self.rows["spectrum","bright_harmonics"]["features"]
        self.assertEqual(a,b)
        self.assertEqual(a["binary_occupancy_fraction"],1)
        self.assertEqual(a["binary_occupancy_entropy_bits"],0)

    def test_encoding_dependency(self):
        a = self.rows["spectrum","odd_harmonics"]["features"]
        self.assertEqual(a["binary_occupancy_fraction"],.6)
        self.assertAlmostEqual(a["binary_occupancy_entropy_bits"],.9709505944546686)

    def test_pair_count_and_uniqueness(self):
        pairs = crossmodal_study()["cross_domain_comparisons"]
        self.assertEqual(len(pairs),207)
        self.assertEqual(len({(tuple(p["first"]),tuple(p["second"])) for p in pairs}),207)
        self.assertTrue(all(p["first"][0] != p["second"][0] for p in pairs))

    def test_symmetry(self):
        for p in crossmodal_study()["cross_domain_comparisons"]:
            a,b = self.rows[tuple(p["first"])],self.rows[tuple(p["second"])]
            reverse = compare(b,a)
            for key in ("absolute_descriptor_differences","exact_descriptor_matches",
                        "undefined_descriptors"):
                self.assertEqual(p[key],reverse[key])

    def test_bounds_and_missingness(self):
        for p in crossmodal_study()["cross_domain_comparisons"]:
            for key,value in p["absolute_descriptor_differences"].items():
                if value is None:
                    self.assertIn(key,p["undefined_descriptors"])
                else:
                    self.assertTrue(0 <= value <= 1)
                    self.assertEqual(value == 0,key in p["exact_descriptor_matches"])

    def test_cli_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]),0)
        self.assertEqual(json.loads(out.getvalue()),crossmodal_study())
        self.assertEqual(crossmodal_study(),crossmodal_study())
