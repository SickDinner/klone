import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase

from klone.research_authoritative_policy import (
    initialize_publication_policy, set_publication_policy,
    enforce_publication_policy)


class AuthoritativePolicyTests(TestCase):
    def test_deny_by_default_and_revocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shared.sqlite"
            initialize_publication_policy(path)
            def check(version):
                with closing(sqlite3.connect(path)) as db:
                    db.execute("BEGIN IMMEDIATE")
                    enforce_publication_policy(db, "reviewer", "claim", version)
            with self.assertRaises(PermissionError):
                check(1)
            set_publication_policy(path, version=2, enabled=True,
                                   members={"reviewer": True})
            check(2)
            with self.assertRaises(PermissionError):
                check(1)
            set_publication_policy(path, version=3, enabled=False,
                                   members={"reviewer": True})
            with self.assertRaises(PermissionError):
                check(3)

    def test_unknown_member_and_rollback_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shared.sqlite"
            set_publication_policy(path, version=2, enabled=True,
                                   members={"reviewer": True})
            with closing(sqlite3.connect(path)) as db:
                db.execute("BEGIN IMMEDIATE")
                with self.assertRaises(PermissionError):
                    enforce_publication_policy(db, "stranger", "claim", 2)
            with self.assertRaises(ValueError):
                set_publication_policy(path, version=2, enabled=True,
                                       members={"stranger": True})
