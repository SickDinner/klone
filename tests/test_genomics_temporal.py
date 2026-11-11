from __future__ import annotations
from dataclasses import replace
from fractions import Fraction
import unittest

from klone.genomics_public import PublicSample
from klone.genomics_temporal import compare_intervals, temporal_pairwise


def sample(accession, start, end):
    return PublicSample(
        accession=accession, source="AADR", publication="doi:test",
        assembly="GRCh37", assay="1240k", region="Northern Europe",
        period_start_ce=start, period_end_ce=end, public_release=True,
        reuse_permitted=True, quality="medium")


class TemporalGenomicsTests(unittest.TestCase):
    def test_disjoint_and_overlap(self):
        a = sample("A", 700, 800)
        b = sample("B", 900, 1000)
        result = compare_intervals(a, b)
        self.assertEqual(result.possible_order, "left_before_right")
        self.assertEqual(result.overlap_fraction, Fraction(0))
        overlapping = compare_intervals(a, sample("C", 750, 850))
        self.assertEqual(overlapping.overlap_years, 51)
        self.assertEqual(overlapping.union_years, 151)
        self.assertEqual(overlapping.overlap_fraction, Fraction(51, 151))
        self.assertIn("no_migration_or_kinship", overlapping.interpretation)

    def test_pairwise_deterministic(self):
        a, b, c = sample("A", 1, 3), sample("B", 2, 4), sample("C", 5, 7)
        self.assertEqual(temporal_pairwise((a, b, c)),
                         temporal_pairwise((c, a, b)))
        self.assertEqual(len(temporal_pairwise((a, b, c))), 3)

    def test_reject_duplicate_or_restricted(self):
        a = sample("A", 700, 800)
        with self.assertRaises(ValueError):
            temporal_pairwise((a, a))
        with self.assertRaises(PermissionError):
            compare_intervals(a, replace(a, reuse_permitted=False))

    def test_bounded_input(self):
        a = sample("A", 700, 800)
        with self.assertRaises(ValueError):
            temporal_pairwise((a, sample("B", 700, 800)), max_samples=1)


if __name__ == "__main__":
    unittest.main()
