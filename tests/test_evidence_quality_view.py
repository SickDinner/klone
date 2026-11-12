import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "klone" / "static"


class EvidenceQualityViewTests(unittest.TestCase):
    def test_quality_and_uncertainty_visible(self):
        script = (ROOT / "evidence-view.js").read_text(encoding="utf-8")
        self.assertIn("data.categories && Array.isArray(data.runs)", script)
        self.assertIn("data.unknown_transition_count", script)
        self.assertIn("c.unknown_transitions", script)
        self.assertIn("data.nodes) && Array.isArray(data.edges)", script)

    def test_no_unsafe_html_or_upload(self):
        script = (ROOT / "evidence-view.js").read_text(encoding="utf-8")
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("fetch(", script)
        self.assertNotIn("eval(", script)

    def test_html_describes_quality(self):
        page = (ROOT / "evidence.html").read_text(encoding="utf-8")
        self.assertIn("Evidence Qualityn", page)
        self.assertIn("Tiedostoa ei lähetetä palvelimelle", page)


if __name__ == "__main__":
    unittest.main()
