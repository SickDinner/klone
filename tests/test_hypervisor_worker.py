from __future__ import annotations

import sys
import unittest

from klone.hypervisor_worker import BoundedWorkerRunner, WorkerExecutionError


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

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            BoundedWorkerRunner(workers={"bad": []})


if __name__ == "__main__":
    unittest.main()
