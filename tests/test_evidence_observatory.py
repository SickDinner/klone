import tempfile
from pathlib import Path
import unittest

from klone.evidence_observatory import collect, render


class EvidenceObservatoryTests(unittest.TestCase):
    def test_empty_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(collect(Path(tmp)), [])
            self.assertIn("KLONE Evidence Observatory", render([]))

    def test_missing_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                collect(Path(tmp) / "missing")

    def test_missing_manifest_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "run-one"
            folder.mkdir()
            results = collect(Path(tmp))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["decision"], "blocked")

    def test_html_escaping(self):
        page = render([{
            "run_name": "<script>alert(1)</script>", "commit": None,
            "integrity_ok": False, "required_stages_passed": False,
            "stage_statuses": {}, "errors": ["<img src=x>"],
            "decision": "blocked",
        }])
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img src=x>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
