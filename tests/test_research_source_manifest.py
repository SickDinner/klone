import unittest

from klone.research_source_manifest import manifest_public_source, verify_public_source


class PublicSourceManifestTests(unittest.TestCase):
    def test_identical_bytes_verify(self):
        source = b"public archive extract"
        manifest = manifest_public_source(source_id="archive:123", content=source)
        self.assertEqual(manifest.byte_length, len(source))
        self.assertTrue(verify_public_source(manifest, source))

    def test_modified_bytes_do_not_verify(self):
        manifest = manifest_public_source(source_id="archive:123", content=b"record A")
        self.assertFalse(verify_public_source(manifest, b"record B"))

    def test_rejects_unsupported_type_and_large_input(self):
        with self.assertRaises(ValueError):
            manifest_public_source(source_id="archive:123", content=b"x",
                                   media_type="application/octet-stream")
        with self.assertRaises(ValueError):
            manifest_public_source(source_id="archive:123", content=b"x" * 2_000_001)


if __name__ == "__main__":
    unittest.main()
