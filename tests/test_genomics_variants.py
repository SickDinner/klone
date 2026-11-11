from __future__ import annotations
from dataclasses import replace
import unittest

from klone.genomics_variants import VariantSite, harmonize_sites, normalize_snv


def site(**changes):
    data = dict(assembly="GRCh38", chromosome="chr1", position=123,
                reference="a", alternate="g", source_accession="PUBLIC-TEST")
    data.update(changes)
    return VariantSite(**data)


class VariantQcTests(unittest.TestCase):
    def test_canonicalize_and_order_independent_hash(self):
        a, b = site(), site(chromosome="2", position=500, reference="C", alternate="T")
        self.assertEqual(normalize_snv(a).chromosome, "1")
        self.assertEqual(normalize_snv(a).reference, "A")
        self.assertEqual(harmonize_sites((a, b))["fingerprint"],
                         harmonize_sites((b, a))["fingerprint"])
        self.assertFalse(harmonize_sites((a, b))["genotype_comparison_ready"])

    def test_reject_mixed_builds(self):
        with self.assertRaisesRegex(ValueError, "liftover"):
            harmonize_sites((site(), site(assembly="GRCh37")))

    def test_conflicting_alleles_are_reported(self):
        result = harmonize_sites((site(), site(alternate="C")))
        self.assertEqual(result["conflicting_loci"], ("1:123",))
        self.assertFalse(result["reference_fasta_verified"])

    def test_reject_invalid_snvs(self):
        for changes in ({"position": True}, {"position": 0},
                        {"reference": "AT"}, {"alternate": "N"},
                        {"reference": "G"}, {"chromosome": "chr23"},
                        {"assembly": "T2T"}, {"source_accession": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_snv(site(**changes))

    def test_empty_inventory_is_safe(self):
        result = harmonize_sites(())
        self.assertIsNone(result["assembly"])
        self.assertEqual(result["unique_records"], 0)


if __name__ == "__main__":
    unittest.main()
