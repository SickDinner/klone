import contextlib
import errno
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from klone import evidence_io
from klone.evidence_artifact_inspector import main
from klone.evidence_io import (EvidenceIOError, directory_handle, json_object,
                              read_bounded, write_new_report, write_report)


class EvidenceIOTests(unittest.TestCase):
    @unittest.skipUnless(evidence_io._DIR_FD and hasattr(os, "O_PATH"),
                         "requires Linux path descriptors")
    def test_root_need_not_be_openable_for_directory_listing(self):
        real_open = os.open

        def deny_root_listing(path, flags, *args, **kwargs):
            if os.fspath(path) == "/" and not flags & os.O_PATH:
                raise PermissionError(errno.EACCES, "root listing denied", "/")
            return real_open(path, flags, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.json"
            source.write_bytes(b"original")
            with patch.object(evidence_io.os, "open", side_effect=deny_root_listing):
                self.assertEqual(read_bounded(source, 100), b"original")
                write_new_report(root / "new" / "report.json", "first", root / "runs")
                runs = root / "runs"
                runs.mkdir()
                write_report(root / "replace" / "report.json", "second", runs)
            self.assertEqual(source.read_bytes(), b"original")
            self.assertEqual((root / "new" / "report.json").read_text(), "first")
            self.assertEqual((root / "replace" / "report.json").read_text(), "second")

    @unittest.skipUnless(evidence_io._DIR_FD and hasattr(os, "O_PATH")
                         and hasattr(os, "geteuid") and os.geteuid() != 0,
                         "requires unprivileged Linux directory permissions")
    def test_read_and_publication_through_search_only_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "search-only"
            reports = parent / "reports"
            reports.mkdir(parents=True)
            source = parent / "source.json"
            source.write_bytes(b"original")
            runs = Path(tmp) / "runs"
            runs.mkdir()
            parent.chmod(0o111)
            try:
                with self.assertRaises(PermissionError):
                    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
                    os.close(descriptor)
                self.assertEqual(read_bounded(source, 100), b"original")
                output = reports / "nested" / "report.json"
                write_new_report(output, "first", runs)
                with self.assertRaises(ValueError):
                    write_new_report(output, "do not replace", runs)
                self.assertEqual(output.read_text(), "first")
                write_report(output, "second", runs)
                self.assertEqual(output.read_text(), "second")
                self.assertEqual(source.read_bytes(), b"original")
            finally:
                parent.chmod(0o700)

    @unittest.skipUnless(evidence_io._DIR_FD, "requires directory descriptors")
    def test_raced_directory_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "parent"
            parent.mkdir()
            outside = root / "outside"
            outside.mkdir()
            original_check = evidence_io.checked_path

            def swap_after_check(path, **kwargs):
                checked = original_check(path, **kwargs)
                if checked == parent:
                    parent.rename(root / "original-parent")
                    parent.symlink_to(outside, target_is_directory=True)
                return checked

            with patch.object(evidence_io, "checked_path", side_effect=swap_after_check):
                with self.assertRaises(OSError):
                    with directory_handle(parent):
                        self.fail("raced symlink must not yield a descriptor")
            self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(evidence_io._DIR_FD and hasattr(os, "O_PATH"),
                         "requires Linux path descriptors")
    def test_directory_descriptors_without_o_path_remain_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source"
            path.write_bytes(b"original")
            with patch.object(evidence_io.os, "O_PATH", 0):
                self.assertEqual(read_bounded(path, 100), b"original")

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
