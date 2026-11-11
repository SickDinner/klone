import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import TestCase

from klone.integrated_research_readonly import main
from klone.integrated_research_cli import main as write_main


class ResearchReadonlyTests(TestCase):
    def test_preview_no_db_and_inspect_saved_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "public"
            source_dir.mkdir()
            (source_dir / "record.txt").write_text("Archive", encoding="utf-8")
            source_index = root / "sources.json"
            source_index.write_text(json.dumps({
                "archive:1": {"file": "record.txt", "media_type": "text/plain"}}))
            dossier = root / "dossier.json"
            dossier.write_text(json.dumps({
                "hypotheses": [{"hypothesis_id": "h", "statement": "Claim"}],
                "evidence": [{
                    "evidence_id": "e", "source_ref": "archive:1",
                    "hypothesis_id": "h", "stance": "supports",
                    "quality": "medium", "rationale": "Record",
                    "dependency_group": "archive"}]}))
            db = root / "research.sqlite"
            args = ["--dossier", str(dossier), "--sources", str(source_index),
                    "--source-dir", str(source_dir)]
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(main(["preview"] + args), 0)
            preview = json.loads(out.getvalue())
            self.assertTrue(preview["database_modified"] is False)
            self.assertFalse(db.exists())
            with redirect_stdout(StringIO()):
                self.assertEqual(write_main([
                    "--database", str(db), "--dossier-id", "demo",
                    *args, "--output-dir", str(root / "out")]), 0)
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(main(["inspect", "--database", str(db),
                                       "--dossier-id", "demo", "--version", "1"]), 0)
            inspected = json.loads(out.getvalue())
            self.assertEqual(inspected["version"], 1)
            self.assertFalse(inspected["source_bytes_reverified"])
            self.assertIn("Claim", inspected["markdown"])

    def test_preview_bad_source_fails_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("public").mkdir()
            root.joinpath("dossier.json").write_text(json.dumps({
                "hypotheses": [{"hypothesis_id": "h", "statement": "Claim"}],
                "evidence": []}))
            root.joinpath("sources.json").write_text("{}")
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(main(["preview", "--dossier", str(root / "dossier.json"),
                    "--sources", str(root / "sources.json"),
                    "--source-dir", str(root / "public")]), 0)
            self.assertEqual(json.loads(out.getvalue())["verified_source_ids"], [])
