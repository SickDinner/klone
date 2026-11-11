from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier_workflow import append_research_dossier, read_research_dossier


class DossierWorkflowTests(unittest.TestCase):
    def test_end_to_end_persistence_and_contradiction_delta(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            h = (Hypothesis("h", "Claim"),)
            supporting = EvidenceItem("e1", "archive:1", "h", "supports",
                                      "medium", "Record", "archive")
            contrary = EvidenceItem("e2", "doi:2", "h", "contradicts",
                                    "high", "Study", "study")
            first = append_research_dossier(database_path=path, dossier_id="case",
                                            hypotheses=h, evidence=(supporting,))
            second = append_research_dossier(database_path=path, dossier_id="case",
                                             hypotheses=h, evidence=(supporting, contrary))
            self.assertEqual((first.version, first.previous_version), (1, None))
            self.assertEqual((second.version, second.previous_version), (2, 1))
            self.assertEqual(second.changes["added_evidence"], ("e2",))
            self.assertEqual(second.changes["new_evaluation"][0]["contradiction_groups"], 1)
            self.assertEqual(len(read_research_dossier(database_path=path,
                                                      dossier_id="case", version=1).evidence), 1)
            self.assertEqual(len(read_research_dossier(database_path=path,
                                                      dossier_id="case", version=2).evidence), 2)


if __name__ == "__main__":
    unittest.main()
