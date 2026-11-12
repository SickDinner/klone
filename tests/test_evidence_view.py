import unittest
from pathlib import Path

from klone.main import create_app, STATIC_DIR


class EvidenceViewTests(unittest.TestCase):
    def test_evidence_route_exists(self):
        app = create_app()
        paths = [getattr(route, "path", None) for route in app.routes]
        self.assertIn("/evidence", paths)

    def test_view_assets_exist(self):
        self.assertTrue((STATIC_DIR / "evidence.html").is_file())
        self.assertTrue((STATIC_DIR / "evidence-view.js").is_file())

    def test_no_upload_or_script_execution(self):
        page = (STATIC_DIR / "evidence.html").read_text(encoding="utf-8")
        script = (STATIC_DIR / "evidence-view.js").read_text(encoding="utf-8")
        self.assertIn("type=\"file\"", page)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("fetch(", script)
        self.assertNotIn("eval(", script)


if __name__ == "__main__":
    unittest.main()
