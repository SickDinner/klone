import json
import unittest

from klone.research_dossier_import import import_public_dossier_json


class DossierImportTests(unittest.TestCase):
    def test_valid_import_and_dependency(self):
        payload = {
            "hypotheses": [{"hypothesis_id": "h", "statement": "A proposed link"}],
            "evidence": [{"evidence_id": "e", "source_ref": "archive:1",
                          "hypothesis_id": "h", "stance": "uncertain",
                          "quality": "unknown", "rationale": "Needs verification",
                          "dependency_group": "original-1"}],
        }
        dossier = import_public_dossier_json(json.dumps(payload))
        self.assertEqual(dossier.evidence[0].source_ref, "archive:1")
        self.assertEqual(dossier.version, 1)

    def test_rejects_unknown_fields_and_unknown_hypothesis(self):
        base = {"hypotheses": [{"hypothesis_id": "h", "statement": "A"}],
                "evidence": []}
        with self.assertRaises(ValueError):
            import_public_dossier_json(json.dumps({**base, "secret": "no"}))
        base["evidence"] = [{"evidence_id": "e", "source_ref": "s",
                             "hypothesis_id": "missing", "stance": "supports",
                             "quality": "low", "rationale": "r",
                             "dependency_group": "g"}]
        with self.assertRaises(ValueError):
            import_public_dossier_json(json.dumps(base))

    def test_rejects_large_payload(self):
        with self.assertRaises(ValueError):
            import_public_dossier_json(" " * 1_000_001)


if __name__ == "__main__":
    unittest.main()
