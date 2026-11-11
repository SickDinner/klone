import json
import tempfile
from pathlib import Path
from unittest import TestCase

from klone.integrated_research_cli import main, _read_sources


class IntegratedResearchCLITests(TestCase):
    def test_offline_end_to_end_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "sources"
            sources.mkdir()
            (sources / "record.txt").write_text("Archival record", encoding="utf-8")
            index = root / "sources.json"
            index.write_text(json.dumps({
                "archive:1": {"file": "record.txt", "media_type": "text/plain"}}))
            dossier = root / "dossier.json"
            dossier.write_text(json.dumps({
                "hypotheses": [{"hypothesis_id": "h", "statement": "Historical claim"}],
                "evidence": [{
                    "evidence_id": "e", "source_ref": "archive:1",
                    "hypothesis_id": "h", "stance": "supports",
                    "quality": "medium", "rationale": "Recorded",
                    "dependency_group": "archive"}]}))
            output = root / "out"
            argv = ["--database", str(root / "research.sqlite"),
                    "--dossier-id", "demo", "--dossier", str(dossier),
                    "--sources", str(index), "--source-dir", str(sources),
                    "--output-dir", str(output)]
            self.assertEqual(main(argv), 0)
            data = json.loads((output / "research-result.json").read_text())
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["verified_source_ids"], ["archive:1"])
            self.assertIn("Historical claim", (output / "research-report.md").read_text())
            self.assertEqual(main(argv), 0)
            self.assertEqual(json.loads(
                (output / "research-result.json").read_text())["version"], 2)

    def test_path_traversal_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "sources"
            sources.mkdir()
            (root / "secret.txt").write_text("private")
            index = root / "sources.json"
            index.write_text(json.dumps({
                "archive:1": {"file": "../secret.txt", "media_type": "text/plain"}}))
            with self.assertRaises(ValueError):
                _read_sources(sources, index)
