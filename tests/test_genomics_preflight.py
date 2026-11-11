import unittest
from klone.genomics_preflight import preflight_vcf

SYNTHETIC = (
    b"##fileformat=VCFv4.2\n"
    b"##contig=<ID=1,length=1000>\n"
    b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC\n"
    b"1\t100\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n"
)


class GenomicsPreflightTests(unittest.TestCase):
    def test_synthetic_vcf_summary_without_sample_id(self):
        result = preflight_vcf(SYNTHETIC, reference_build="GRCh38")
        self.assertEqual(result.variant_count, 1)
        self.assertEqual(result.sample_count, 1)
        self.assertEqual(result.contig_count, 1)
        self.assertNotIn("SYNTHETIC", str(result))

    def test_unknown_reference_build_denied(self):
        with self.assertRaisesRegex(ValueError, "reference_build_required"):
            preflight_vcf(SYNTHETIC, reference_build="unknown")

    def test_missing_header_denied(self):
        with self.assertRaises(ValueError):
            preflight_vcf(b"1\t100\t.\tA\tG\t.\tPASS\t.\n", reference_build="GRCh38")

    def test_bad_position_denied(self):
        with self.assertRaisesRegex(ValueError, "vcf_position_invalid"):
            preflight_vcf(SYNTHETIC.replace(b"1\t100\t", b"1\tzero\t"), reference_build="GRCh38")

    def test_oversized_input_denied(self):
        with self.assertRaisesRegex(ValueError, "vcf_size_invalid"):
            preflight_vcf(b"x" * (8 * 1024 * 1024 + 1), reference_build="GRCh38")


if __name__ == "__main__":
    unittest.main()
