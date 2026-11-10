from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from klone.research_ui import serve_research_ui


class ResearchUITests(unittest.TestCase):
    def test_rejects_missing_root(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                serve_research_ui(root=Path(tmp) / "missing",
                                  database_path=Path(tmp) / "audit.sqlite")

    def test_binds_only_loopback(self):
        addresses = []
        class FakeServer:
            def __init__(self, address, handler):
                addresses.append(address)
                self.address = address
                self.server_port = address[1]
            def serve_forever(self):
                pass
            def server_close(self):
                pass
        with TemporaryDirectory() as tmp:
            with patch("klone.research_ui.ThreadingHTTPServer", FakeServer):
                serve_research_ui(root=Path(tmp),
                                  database_path=Path(tmp) / "audit.sqlite", port=8766)
            self.assertEqual(addresses, [("127.0.0.1", 8766)])


if __name__ == "__main__":
    unittest.main()
