import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.research_dossier_pipeline import run_public_dossier_pipeline
from klone.research_dossier_workflow import read_research_dossier


class DossierPipelineTests(unittest.TestCase):
    def test_import_persist_compare_review(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            base = {"hypotheses": [{"hypothesis_id": "h", "statement": "Possible connection"}],
                    "evidence": [{"evidence_id": "e1", "source_ref": "archive:1",
                                  "hypothesis_id": "h", "stance": "supports",
                                  "quality": "medium", "rationale": "Record",
                                  "dependency_group": "archive"}]}
            first = run_public_dossier_pipeline(database_path=db, dossier_id="case",
                                                json_text=json.dumps(base))
            self.assertEqual(first.change.version, 1)
            self.assertEqual(first.review.contradictions, ())
            base["evidence"].append({"evidence_id": "e2", "source_ref": "study:2",
                                     "hypothesis_id": "h", "stance": "contradicts",
                                     "quality": "high", "rationale": "Independent study",
                                     "dependency_group": "study"})
            second = run_public_dossier_pipeline(database_path=db, dossier_id="case",
                                                 json_text=json.dumps(base))
            self.assertEqual(second.change.changes["added_evidence"], ("e2",))
            self.assertEqual(second.review.contradictions, ("h",))
            self.assertEqual(len(read_research_dossier(database_path=db,
                                                      dossier_id="case", version=1).evidence), 1)

    def test_invalid_import_does_not_create_database(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            with self.assertRaises(ValueError):
                run_public_dossier_pipeline(database_path=db, dossier_id="case",
                                            json_text='{"evidence":[]}')
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
