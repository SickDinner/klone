import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier import build_dossier
from klone.research_source_manifest import manifest_public_source
from klone.research_source_link import verify_dossier_sources


class DossierSourceLinkTests(unittest.TestCase):
    def test_verified_missing_and_mismatched_sources(self):
        h = (Hypothesis("h", "Claim"),)
        e = tuple(EvidenceItem(f"e{i}", f"source:{i}", "h", "uncertain",
                               "unknown", "Review", f"group:{i}") for i in range(3))
        dossier = build_dossier(version=1, hypotheses=h, evidence=e)
        manifests = {
            "source:0": manifest_public_source(source_id="source:0", content=b"archive"),
            "source:2": manifest_public_source(source_id="source:2", content=b"original"),
        }
        result = verify_dossier_sources(dossier, manifests, {
            "source:0": b"archive", "source:2": b"changed",
        })
        self.assertEqual(result.verified, ("source:0",))
        self.assertEqual(result.missing, ("source:1",))
        self.assertEqual(result.mismatched, ("source:2",))


if __name__ == "__main__":
    unittest.main()
