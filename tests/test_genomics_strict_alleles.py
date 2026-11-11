from __future__ import annotations
from dataclasses import replace
import unittest

from klone.genomics_variants import VariantSite, normalize_snv


class StrictSNVAllelesTests(unittest.TestCase):
    def test_empty_and_multibase_alleles_fail_closed(self):
        valid = VariantSite("GRCh38", "1", 1234, "A", "G", "public:1")
        for ref, alt in (("", "G"), ("A", ""), ("", ""), ("AA", "G"), ("A", "GG")):
            with self.subTest(ref=ref, alt=alt):
                with self.assertRaises(ValueError):
                    normalize_snv(replace(valid, reference=ref, alternate=alt))

    def test_lowercase_single_base_normalized(self):
        site = VariantSite("GRCh38", "chr1", 1234, "a", "g", "public:1")
        normalized = normalize_snv(site)
        self.assertEqual((normalized.reference, normalized.alternate), ("A", "G"))


if __name__ == "__main__":
    unittest.main()
