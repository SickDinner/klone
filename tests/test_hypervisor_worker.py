from __future__ import annotations

import sys
import unittest

from klone.hypervisor_worker import BoundedWorkerRunner, WorkerExecutionError


@unittest.skipIf(sys.platform == "win32", "POSIX-only bounded worker; Windows disabled fail-closed")
class WorkerTests(unittest.TestCase):
    def test_fixed_worker_json(self):
        runner = BoundedWorkerRunner(
            workers={"echo": [sys.executable, "-c", "print('{\"ok\": true}')"]},
        )
        self.assertEqual(runner.run("echo").payload, {"ok": True})

    def test_unknown_worker_denied(self):
        runner = BoundedWorkerRunner(workers={"echo": [sys.executable, "-c", "print('{}')"]})
        with self.assertRaises(WorkerExecutionError):
            runner.run("other")

    def test_timeout(self):
        runner = BoundedWorkerRunner(
            workers={"sleep": [sys.executable, "-c", "import time; time.sleep(2)"]},
            timeout_seconds=0.1,
        )
        with self.assertRaises(WorkerExecutionError):
            runner.run("sleep")

    def test_output_limit(self):
        runner = BoundedWorkerRunner(
            workers={"large": [sys.executable, "-c", "print('{\"data\": \"' + 'x'*100 + '\"}')"]},
            max_output_bytes=20,
        )
        with self.assertRaises(WorkerExecutionError):
            runner.run("large")

    def test_non_json_rejected(self):
        runner = BoundedWorkerRunner(
            workers={"bad": [sys.executable, "-c", "print('not json')"]},
        )
        with self.assertRaises(WorkerExecutionError):
            runner.run("bad")

    @unittest.skipIf(sys.platform == "win32", "POSIX process-group test")
    def test_nonzero_exit_rejected(self):
        runner = BoundedWorkerRunner(
            workers={"exit": [sys.executable, "-c", "raise SystemExit(3)"]},
        )
        with self.assertRaises(WorkerExecutionError):
            runner.run("exit")

    def test_non_object_json_rejected(self):
        runner = BoundedWorkerRunner(
            workers={"list": [sys.executable, "-c", "print('[]')"]},
        )
        with self.assertRaises(WorkerExecutionError):
            runner.run("list")

    @unittest.skipIf(sys.platform == "win32", "POSIX process-group test")
    def test_child_process_is_killed_on_timeout(self):
        import os
        import tempfile
        import time
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "child-marker"
            child_code = (
                "import pathlib,time; time.sleep(0.8); "
                f"pathlib.Path({str(marker)!r}).write_text('escaped')"
            )
            parent_code = (
                "import subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{child_code!r}]); "
                "time.sleep(5)"
            )
            runner = BoundedWorkerRunner(
                workers={"parent": [sys.executable, "-c", parent_code]},
                timeout_seconds=0.2,
            )
            with self.assertRaises(WorkerExecutionError):
                runner.run("parent")
            time.sleep(1.0)
            self.assertFalse(marker.exists(), "Timed-out child escaped process group")

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            BoundedWorkerRunner(workers={"bad": []})


class WindowsFailClosedTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows-specific guard")
    def test_windows_rejects_worker_before_launch(self):
        from unittest.mock import patch
        runner = BoundedWorkerRunner(
            workers={"echo": [sys.executable, "-c", "print('{}')"]},
        )
        with patch("klone.hypervisor_worker.subprocess.Popen") as popen:
            with self.assertRaisesRegex(WorkerExecutionError, "Windows is disabled"):
                runner.run("echo")
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
