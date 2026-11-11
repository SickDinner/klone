from __future__ import annotations
from dataclasses import replace
import unittest

from klone.genomics_public import PublicSample, catalog_fingerprint, compare_public_metadata


def sample(accession: str = "A") -> PublicSample:
    return PublicSample(
        accession=accession, source="AADR", publication="doi:example",
        assembly="GRCh37", assay="1240k", region="Northern Europe",
        period_start_ce=700, period_end_ce=900, public_release=True,
        reuse_permitted=True, quality="medium", y_haplogroup="I1",
    )


class PublicGenomicsTests(unittest.TestCase):
    def test_deterministic_order_independent_catalog(self):
        a, b = sample(), sample("B")
        self.assertEqual(catalog_fingerprint((a, b)), catalog_fingerprint((b, a)))
        self.assertNotEqual(catalog_fingerprint((a,)), catalog_fingerprint((a, b)))
        with self.assertRaises(ValueError):
            catalog_fingerprint((a, a))

    def test_fail_closed_for_nonpublic_and_restricted(self):
        for change in ({"public_release": False}, {"reuse_permitted": False}):
            with self.subTest(change=change), self.assertRaises(PermissionError):
                catalog_fingerprint((replace(sample(), **change),))

    def test_no_kinship_from_haplogroup(self):
        result = compare_public_metadata(sample(), sample("B"))
        self.assertTrue(result["y_label_equal"])
        self.assertFalse(result["direct_genotype_comparison_ready"])
        self.assertEqual(result["kinship_inference"], "not_supported_by_metadata")

    def test_mixed_assemblies_never_marked_ready(self):
        result = compare_public_metadata(sample(), replace(sample("B"), assembly="GRCh38"))
        self.assertFalse(result["metadata_comparable"])
        self.assertFalse(result["direct_genotype_comparison_ready"])

    def test_rejects_invalid_dates_and_assemblies(self):
        for change in ({"period_start_ce": True}, {"period_end_ce": 600},
                       {"assembly": "unknown"}, {"quality": "perfect"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                catalog_fingerprint((replace(sample(), **change),))


if __name__ == "__main__":
    unittest.main()
