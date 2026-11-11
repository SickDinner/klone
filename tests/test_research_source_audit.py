import unittest

from klone.research_source_audit import audit_public_sources
from klone.research_source_manifest import manifest_public_source


class SourceAuditTests(unittest.TestCase):
    def test_coverage_and_integrity(self):
        expected = {
            "a": manifest_public_source(source_id="a", content=b"A"),
            "b": manifest_public_source(source_id="b", content=b"B"),
            "c": manifest_public_source(source_id="c", content=b"C"),
        }
        result = audit_public_sources(expected=expected,
                                      supplied={"a": b"A", "b": b"wrong", "extra": b"E"})
        self.assertEqual(result.verified, ("a",))
        self.assertEqual(result.missing, ("c",))
        self.assertEqual(result.changed, ("b",))
        self.assertEqual(result.unexpected, ("extra",))

    def test_mismatched_manifest_key_fails(self):
        manifest = manifest_public_source(source_id="a", content=b"A")
        with self.assertRaises(ValueError):
            audit_public_sources(expected={"wrong": manifest}, supplied={})


if __name__ == "__main__":
    unittest.main()
