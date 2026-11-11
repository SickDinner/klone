from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier_store import DossierStore


class DossierStoreTests(unittest.TestCase):
    def test_append_versions_and_preserve_original(self):
        with TemporaryDirectory() as tmp:
            store = DossierStore(Path(tmp) / "research.sqlite")
            hypotheses = (Hypothesis("h", "Claim"),)
            evidence = (EvidenceItem("e", "archive:1", "h", "supports",
                                     "medium", "Record", "archive-1"),)
            self.assertEqual(store.append(dossier_id="case-1", hypotheses=hypotheses,
                                          evidence=()), 1)
            self.assertEqual(store.append(dossier_id="case-1", hypotheses=hypotheses,
                                          evidence=evidence), 2)
            self.assertEqual(store.read(dossier_id="case-1", version=1),
                             (hypotheses, ()))
            self.assertEqual(store.read(dossier_id="case-1", version=2),
                             (hypotheses, evidence))

    def test_detect_modified_evidence(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            store = DossierStore(path)
            store.append(dossier_id="case-1",
                         hypotheses=(Hypothesis("h", "Claim"),), evidence=())
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE research_dossier_snapshots SET canonical_json=?",
                           ('{"hypotheses":[],"evidence":[]}',))
            with self.assertRaises(ValueError):
                store.read(dossier_id="case-1", version=1)

    def test_missing_version_fails_closed(self):
        with TemporaryDirectory() as tmp:
            store = DossierStore(Path(tmp) / "research.sqlite")
            with self.assertRaisesRegex(ValueError, "not found"):
                store.read(dossier_id="case-1", version=1)


if __name__ == "__main__":
    unittest.main()
