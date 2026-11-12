import importlib.util
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "backup_local.py"
SPEC = importlib.util.spec_from_file_location("klone_backup_local", SCRIPT)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


class BackupLocalTests(unittest.TestCase):
    def test_missing_database_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"KLONE_DATA_DIR": folder, "KLONE_DB_PATH": str(Path(folder) / "missing.db")}):
                self.assertEqual(backup.main(), 2)
            self.assertFalse((Path(folder) / "backups").exists())

    def test_backup_is_integrity_checked_and_contains_records(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "klone_mission_control.db"
            with closing(sqlite3.connect(database)) as conn:
                with conn:
                    conn.execute("CREATE TABLE sample (value TEXT)")
                    conn.execute("INSERT INTO sample VALUES ('local-only')")
            with patch.dict(os.environ, {"KLONE_DATA_DIR": folder, "KLONE_DB_PATH": str(database)}):
                self.assertEqual(backup.main(), 0)
            files = list((Path(folder) / "backups").glob("*.sqlite3"))
            self.assertEqual(len(files), 1)
            with closing(sqlite3.connect(files[0])) as conn:
                self.assertEqual(conn.execute("SELECT value FROM sample").fetchone()[0], "local-only")
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
