import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "local_deploy.py"
SPEC = importlib.util.spec_from_file_location("klone_local_deploy", SCRIPT)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


class LocalDeployTests(unittest.TestCase):
    def test_doctor_on_checkout(self):
        self.assertEqual(deploy.doctor(), 0)

    def test_invalid_port_denied_without_starting_server(self):
        with patch.object(deploy, "python_path", return_value=Path(__file__)):
            self.assertEqual(deploy.start(80), 2)

    def test_invalid_port_never_checks_dependencies(self):
        with patch.object(deploy, "dependencies_ready", side_effect=AssertionError("must not run")):
            for port in (0, 80, 1023, 65536, -1):
                with self.subTest(port=port):
                    self.assertEqual(deploy.start(port), 2)

    def test_missing_virtualenv_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(deploy, "python_path", return_value=Path(temp) / "missing"):
                self.assertEqual(deploy.start(8000), 2)

    def test_loopback_only(self):
        self.assertEqual(deploy.HOST, "127.0.0.1")

    def test_healthcheck_rejects_wrong_service(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, count):
                return b'{"status":"ok","app_version":null}'
        with patch.object(deploy.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual(deploy.healthcheck(), 1)

    def test_healthcheck_accepts_valid_klone_response(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, count):
                return b'{"status":"ok","app_version":"0.2.0"}'
        with patch.object(deploy.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual(deploy.healthcheck(), 0)

    def test_parser_rejects_unknown_action(self):
        with self.assertRaises(SystemExit):
            deploy.main(["deploy-to-internet"])


if __name__ == "__main__":
    unittest.main()
