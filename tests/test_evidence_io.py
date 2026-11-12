import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from klone.evidence_artifact_inspector import main
from klone.evidence_io import EvidenceIOError, json_object, read_bounded, write_report


class EvidenceIOTests(unittest.TestCase):
    def test_report_cannot_replace_original_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            run = root / "run-1"
            run.mkdir(parents=True)
            artifact = run / "run.json"
            artifact.write_bytes(b"original")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--runs-root", str(root), "--output", str(artifact)])
            self.assertEqual(artifact.read_bytes(), b"original")

    def test_report_replaces_only_external_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            root.mkdir()
            output = Path(tmp) / "reports" / "report.json"
            write_report(output, "first", root)
            write_report(output, "second", root)
            self.assertEqual(output.read_text(), "second")
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(list(output.parent.iterdir()), [output])

    def test_parent_symlink_cannot_redirect_output_into_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            root.mkdir()
            alias = Path(tmp) / "alias"
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                write_report(alias / "report.json", "bad", root)
            self.assertEqual(list(root.iterdir()), [])

    def test_parent_symlink_cannot_redirect_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real"
            target.mkdir()
            (target / "log").write_bytes(b"private")
            alias = root / "alias"
            alias.symlink_to(target, target_is_directory=True)
            with self.assertRaises(EvidenceIOError):
                read_bounded(alias / "log", 1024)

    def test_read_limits_empty_and_oversized_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log"
            path.write_bytes(b"")
            self.assertEqual(read_bounded(path, 0), b"")
            path.write_bytes(b"12345")
            with self.assertRaises(EvidenceIOError) as error:
                read_bounded(path, 4)
            self.assertEqual(error.exception.code, "oversized")
            self.assertEqual(path.read_bytes(), b"12345")

    def test_output_symlink_never_mutates_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            root.mkdir()
            original = Path(tmp) / "original"
            original.write_text("original")
            alias = Path(tmp) / "out.json"
            alias.symlink_to(original)
            with self.assertRaises(ValueError):
                write_report(alias, "bad", root)
            self.assertEqual(original.read_text(), "original")

    def test_strict_json_rejects_duplicate_keys_nonfinite_and_nonobjects(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'"text"'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                json_object(raw)
        self.assertEqual(json_object(b'{"a":1}'), {"a": 1})

    def test_missing_file_has_distinct_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(EvidenceIOError) as error:
                read_bounded(Path(tmp) / "missing", 10)
            self.assertEqual(error.exception.code, "missing")
