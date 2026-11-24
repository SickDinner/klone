"""KLONE v3.4.3: regressions for explicit closure of fd-inspection test DBs.

This test re-executes the isolated red-team fixture against tracked sqlite3
connections. It checks actual close() calls, not a fragile GC warning schedule.
No live database, production path, service or authorization is involved.
"""
from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from test_approval_storage_fd_v23 import StorageV23PosixTests, _SUPPORTED


class _TrackedConnection(sqlite3.Connection):
    close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        super().close()


@unittest.skipUnless(_SUPPORTED, "requires Linux/Android fd isolation test support")
class SQLiteFixtureClosureV343Tests(unittest.TestCase):
    def test_red_team_fixture_closes_all_three_sqlite_connections(self):
        original_connect = sqlite3.connect
        opened = []

        def tracked_connect(*args, **kwargs):
            # The red-team fixture passes neither a factory nor external DB paths.
            self.assertNotIn("factory", kwargs)
            conn = original_connect(*args, factory=_TrackedConnection, **kwargs)
            opened.append(conn)
            return conn

        # This reruns the original assertion: same-UID raw SQLite writes remain
        # possible despite descriptor-anchored inspection. Only fixture
        # connection lifecycle changes, not the authorization semantics.
        fixture = StorageV23PosixTests(
            "test_snapshot_does_not_prevent_same_uid_raw_sqlite_update")
        result = unittest.TestResult()
        with patch("sqlite3.connect", side_effect=tracked_connect):
            fixture.run(result)

        self.assertTrue(result.wasSuccessful(), "original red-team fixture must pass")
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(opened), 3, "all three original SQLite connections observed")
        for conn in opened:
            self.assertEqual(conn.close_calls, 1, "connection must be explicitly closed once")
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
