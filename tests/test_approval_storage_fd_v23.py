"""Offline, isolated fd-anchored inspection tests; no production DB used."""
from __future__ import annotations

from contextlib import closing

import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from klone.approval_storage_fd_v23 import (
    StorageIsolationUnavailable,
    VerifiedStorageSnapshot,
    inspect_private_approval_storage,
    inspect_private_approval_storage_at,
    _parts,
    _relative_parts,
)


class StorageV23PortableTests(unittest.TestCase):
    def test_bad_path_spellings_fail_before_io(self):
        for path in ("relative.db", "/", "/a//b", "/a/../b", "/a/./b",
                     "/a/b/", "/a/\x00b", "", None, 3):
            with self.subTest(path=path), self.assertRaises(StorageIsolationUnavailable):
                _parts(path)

    def test_not_a_production_approval_interface(self):
        import klone.approval_storage_fd_v23 as m
        for method in ("approve", "revoke", "publish", "activate", "sqlite_connect"):
            self.assertFalse(hasattr(m, method))

    def test_no_descriptor_support_fails_closed(self):
        with patch("klone.approval_storage_fd_v23._requirements", side_effect=StorageIsolationUnavailable("no")):
            with self.assertRaises(StorageIsolationUnavailable):
                inspect_private_approval_storage("/tmp/approval.sqlite")


_SUPPORTED = (os.name == "posix" and all(hasattr(os, key) for key in
  ("O_PATH", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK", "geteuid"))
  and os.open in getattr(os, "supports_dir_fd", ())
  and os.stat in getattr(os, "supports_dir_fd", ()))


@unittest.skipUnless(_SUPPORTED, "requires Linux/Android dirfd and O_NOFOLLOW")
class StorageV23PosixTests(unittest.TestCase):
    def setUp(self):
        # Avoid /tmp's world-writable ancestor, which the policy rejects.
        # Termux may alias /data/data to /data/user/0 via a system symlink.
        # Use the canonical trusted test home, never an untrusted user path.
        self.tmp = tempfile.TemporaryDirectory(prefix="klone-v23-", dir=Path.home().resolve(strict=True))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "approval.sqlite3"
        self.db.write_bytes(b"LAB-ONLY DATABASE FIXTURE")
        os.chmod(self.root, 0o700)
        os.chmod(self.db, 0o600)
        # A trusted host retains a capability to its private application root.
        # Android /data group ownership is checked by the OS, not by
        # re-walking that system-managed prefix from '/'.
        flags = os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        self.root_fd = os.open(self.root, flags)
        self.addCleanup(os.close, self.root_fd)

    def verified(self):
        return inspect_private_approval_storage_at(self.root_fd, self.db.name)

    def test_trusted_root_fd_remains_caller_owned(self):
        with self.verified() as snap:
            self.assertEqual(snap.database_inode[1], self.db.stat().st_ino)
        # Snapshot closes its duplicate, never the caller's root capability.
        self.assertTrue(stat.S_ISDIR(os.fstat(self.root_fd).st_mode))

    def test_untrusted_fd_denied(self):
        for fd in (-1, None, True):
            with self.subTest(fd=fd), self.assertRaises(StorageIsolationUnavailable):
                inspect_private_approval_storage_at(fd, self.db.name)
        with self.assertRaises(StorageIsolationUnavailable):
            inspect_private_approval_storage_at(self.root_fd, "../approval.sqlite3")

    def test_private_file_and_no_sidecars(self):
        with self.verified() as snap:
            self.assertEqual(snap.database_inode[1], self.db.stat().st_ino)
            self.assertEqual(snap.sidecars, {})
            snap.check_names_unchanged()
        with self.assertRaisesRegex(StorageIsolationUnavailable, "snapshot_closed"):
            snap.check_names_unchanged()

    def test_existing_private_wal_shm_journal(self):
        for suffix in ("-wal", "-shm", "-journal"):
            path = Path(str(self.db) + suffix)
            path.write_bytes(suffix.encode("ascii"))
            os.chmod(path, 0o600)
        with self.verified() as snap:
            self.assertEqual(len(snap.sidecars), 3)
            snap.check_names_unchanged()
            for name, (fd, identity) in snap.sidecars.items():
                self.assertEqual(os.fstat(fd).st_ino, identity[1], name)

    def test_missing_database_denied(self):
        self.db.unlink()
        with self.assertRaises(StorageIsolationUnavailable):
            self.verified()

    def test_database_symlink_denied(self):
        dst = self.root / "actual.db"
        self.db.rename(dst)
        self.db.symlink_to(dst)
        with self.assertRaises(StorageIsolationUnavailable):
            self.verified()

    def test_ancestor_symlink_denied(self):
        link = self.root / "alias"
        inner = self.root / "private"
        inner.mkdir(mode=0o700)
        db = inner / "db.sqlite3"
        db.write_bytes(b"fixture")
        os.chmod(db, 0o600)
        link.symlink_to(inner, target_is_directory=True)
        with self.assertRaises(StorageIsolationUnavailable):
            inspect_private_approval_storage_at(self.root_fd, "alias/db.sqlite3")

    def test_private_directory_required(self):
        os.chmod(self.root, 0o755)
        with self.assertRaisesRegex(StorageIsolationUnavailable, "private_directory_required"):
            self.verified()

    def test_ancestor_must_not_be_writable_to_other_identities(self):
        unsafe = self.root / "other_writable"
        unsafe.mkdir(mode=0o777)
        os.chmod(unsafe, 0o777)
        leaf = unsafe / "private"
        leaf.mkdir(mode=0o700)
        db = leaf / "approval.sqlite3"
        db.write_bytes(b"fixture")
        os.chmod(db, 0o600)
        with self.assertRaisesRegex(StorageIsolationUnavailable, "writable_ancestor"):
            inspect_private_approval_storage_at(self.root_fd, "other_writable/private/approval.sqlite3")

    def test_database_public_permissions_denied(self):
        for mode in (0o644, 0o666, 0o400):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.db, mode)
                with self.assertRaises(StorageIsolationUnavailable):
                    self.verified()

    def test_wal_public_permissions_denied(self):
        sidecar = Path(str(self.db) + "-wal")
        sidecar.write_bytes(b"fixture")
        os.chmod(sidecar, 0o644)
        with self.assertRaises(StorageIsolationUnavailable):
            self.verified()

    def test_wal_symlink_denied(self):
        sidecar = Path(str(self.db) + "-wal")
        sidecar.symlink_to(self.db)
        with self.assertRaises(StorageIsolationUnavailable):
            self.verified()

    def test_shm_fifo_denied(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("requires mkfifo")
        os.mkfifo(str(self.db) + "-shm", mode=0o600)
        with self.assertRaises(StorageIsolationUnavailable):
            self.verified()

    def test_hardlinked_database_denied(self):
        if not hasattr(os, "link"):
            self.skipTest("os.link is not available on this Python build")
        other = self.root / "hardlink.db"
        os.link(self.db, other)
        with self.assertRaises(StorageIsolationUnavailable):
            self.verified()

    def test_names_rebound_after_open_are_detected(self):
        with self.verified() as snap:
            original = snap.database_inode
            archived = self.root / "archive.db"
            self.db.rename(archived)
            self.db.write_bytes(b"substitute")
            os.chmod(self.db, 0o600)
            self.assertEqual(os.fstat(snap.database_fd).st_ino, original[1])
            with self.assertRaisesRegex(StorageIsolationUnavailable, "storage_name_changed"):
                snap.check_names_unchanged()

    def test_sidecar_added_after_snapshot_is_detected(self):
        with self.verified() as snap:
            sidecar = Path(str(self.db) + "-wal")
            sidecar.write_bytes(b"extra")
            os.chmod(sidecar, 0o600)
            with self.assertRaisesRegex(StorageIsolationUnavailable, "storage_name_changed"):
                snap.check_names_unchanged()

    def test_close_idempotent(self):
        snap = self.verified()
        db_fd = snap.database_fd
        snap.close()
        snap.close()
        with self.assertRaises(OSError):
            os.fstat(db_fd)
        with self.assertRaises(StorageIsolationUnavailable):
            snap.__enter__()

    def test_snapshot_does_not_prevent_same_uid_raw_sqlite_update(self):
        # Red-team finding: fds are inspection snapshots, NOT a DB write ACL.
        # sqlite3.Connection.__exit__ commits/rolls back but does not close;
        # explicit closing is required for all three temporary test connections.
        import sqlite3
        self.db.unlink()
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("CREATE TABLE proposals (state TEXT)")
            db.execute("INSERT INTO proposals VALUES ('awaiting_approval')")
        os.chmod(self.db, 0o600)
        with self.verified() as snap:
            with closing(sqlite3.connect(self.db)) as writer, writer:
                writer.execute("UPDATE proposals SET state='approved'")
            with closing(sqlite3.connect(self.db)) as reader, reader:
                self.assertEqual(reader.execute("SELECT state FROM proposals").fetchone()[0],
                                 "approved")
            # Even if unchanged, its inode is writable by the SAME UID.
            snap.check_names_unchanged()

    def test_existing_real_sqlite_wal_and_shm_inspected(self):
        import sqlite3
        # WAL sidecar files are present while writer is still alive.
        self.db.unlink()
        con = sqlite3.connect(self.db)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("CREATE TABLE x (id INTEGER PRIMARY KEY)")
            con.execute("INSERT INTO x VALUES (1)")
            con.commit()
            for suffix in ("-wal", "-shm"):
                p = Path(str(self.db) + suffix)
                self.assertTrue(p.exists(), suffix)
                os.chmod(p, 0o600)
            os.chmod(self.db, 0o600)
            with self.verified() as snap:
                self.assertTrue(any(k.endswith("-wal") for k in snap.sidecars))
                self.assertTrue(any(k.endswith("-shm") for k in snap.sidecars))
        finally:
            con.close()

if __name__ == "__main__":
    unittest.main()
