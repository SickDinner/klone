from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from klone.research_cli import main


class ResearchCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "note.md").write_text("DNA archaeology evidence", encoding="utf-8")
        self.db = self.root / "audit.sqlite"

    def args(self):
        return ["--root", str(self.root), "--file", "note.md",
                "--question", "DNA", "--database", str(self.db),
                "--trace-id", "cli-1"]

    def test_cli_creates_report_and_audit(self):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(self.args())
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn("DNA archaeology evidence", out.getvalue())
        self.assertIn("Audit events", err.getvalue())
        self.assertTrue(self.db.exists())

    def test_cli_rejects_nonpublic_room(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                main(self.args() + ["--room", "restricted-room"])

    def test_cli_does_not_expose_exception_details(self):
        err = StringIO()
        with redirect_stderr(err):
            code = main(self.args() + ["--file", "missing.md"])
        self.assertEqual(code, 1)
        self.assertNotIn(str(self.root), err.getvalue())


if __name__ == "__main__":
    unittest.main()
