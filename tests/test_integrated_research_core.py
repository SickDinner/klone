import json
import tempfile
from pathlib import Path
from unittest import TestCase

from klone.integrated_research_core import run_integrated_public_research
from klone.research_source_manifest import manifest_public_source
from klone.research_dossier_workflow import read_research_dossier


def sample_json():
    return json.dumps({
        "hypotheses": [{"hypothesis_id": "h", "statement": "Historical claim"}],
        "evidence": [{
            "evidence_id": "e", "source_ref": "archive:1",
            "hypothesis_id": "h", "stance": "supports",
            "quality": "medium", "rationale": "Documented record",
            "dependency_group": "archive"}]})


class IntegratedResearchCoreTests(TestCase):
    def test_verified_source_persists_and_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            args = dict(database_path=db, dossier_id="demo",
                json_text=sample_json(),
                manifests={"archive:1": manifest_public_source(
                    source_id="archive:1", content=b"document")},
                source_bytes={"archive:1": b"document"})
            first = run_integrated_public_research(**args)
            self.assertEqual(first.change.version, 1)
            self.assertEqual(first.report.verified_source_ids, ("archive:1",))
            self.assertIn("Historical claim", first.report.markdown)
            second = run_integrated_public_research(**args)
            self.assertEqual(second.change.version, 2)
            self.assertEqual(read_research_dossier(
                database_path=db, dossier_id="demo", version=1).fingerprint,
                read_research_dossier(
                    database_path=db, dossier_id="demo", version=2).fingerprint)

    def test_missing_or_changed_source_does_not_create_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            manifest = manifest_public_source(
                source_id="archive:1", content=b"document")
            for sources in ({}, {"archive:1": b"altered"}):
                with self.subTest(sources=sources):
                    with self.assertRaises(ValueError):
                        run_integrated_public_research(
                            database_path=db, dossier_id="demo",
                            json_text=sample_json(),
                            manifests={"archive:1": manifest},
                            source_bytes=sources)
                    self.assertFalse(db.exists())


if __name__ == "__main__":
    import unittest
    unittest.main()
