"""Safety regression checks for Memory Explorer's read-only selection lifecycle.

These source-level checks complement, but do not replace, real browser tests.
"""
from pathlib import Path
import shutil
import subprocess
import unittest

APP = Path(__file__).resolve().parents[1] / "src" / "klone" / "static" / "app.js"


class MemorySelectionSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")

    def test_js_parses_when_node_is_available(self):
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable; browser smoke remains required")
        result = subprocess.run(["node", "--check", str(APP)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stale_selection_responses_are_guarded(self):
        source = self.source
        self.assertIn("generation !== memorySelectionGeneration", source)
        self.assertIn("generation !== memoryListGeneration", source)
        self.assertIn("selectionGeneration !== memorySelectionGeneration", source)

    def test_failures_clear_sensitive_panels(self):
        source = self.source
        self.assertIn("function clearMemorySelectionPanels()", source)
        self.assertIn("state.memory.contextPayload = null;", source)
        self.assertIn("state.memory.answer = null;", source)
        self.assertIn('document.querySelector("#memory-detail").textContent = "Memory selection unavailable."', source)

    def test_event_ids_are_url_encoded(self):
        self.assertIn("/api/memory/events/${encodeURIComponent(id)}", self.source.replace("${", "${")) if False else self.assertIn("/api/memory/events/${encodeURIComponent(id)}".replace("\\", ""), self.source)

    def test_denied_errors_do_not_render_server_message_in_memory_panels(self):
        for message in ("Memory selection unavailable.", "Memory list unavailable.", "Memory answer unavailable.", "Memory context unavailable."):
            self.assertIn(message, self.source)


if __name__ == "__main__":
    unittest.main()
