"""Lab tests for preflight only; synthetic UIDs never prove real UID separation."""
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from klone.approval_owner_boundary_v22 import (
    OwnerIsolationUnavailable, kernel_peer_uid, require_isolated_approval_owner,
)


class OwnerBoundaryV22Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="klone-v22-uid-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "approvals.sqlite3"
        self.db.write_bytes(b"LAB ONLY - NOT SQLITE")
        os.chmod(self.dir, 0o700)
        os.chmod(self.db, 0o600)
        self.sock, self.peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(self.sock.close)
        self.addCleanup(self.peer.close)

    def test_real_same_uid_socket_denied(self):
        # This must be denied on Termux; a second Termux session is not isolated.
        self.assertEqual(kernel_peer_uid(self.sock), os.geteuid())
        with self.assertRaisesRegex(OwnerIsolationUnavailable, "same_uid_not_isolated"):
            require_isolated_approval_owner(self.sock, self.db)

    def test_non_unix_socket_denied(self):
        with self.assertRaises(OwnerIsolationUnavailable):
            kernel_peer_uid(object())

    def test_reject_world_readable_database(self):
        os.chmod(self.db, 0o644)
        with patch("klone.approval_owner_boundary_v22.kernel_peer_uid", return_value=os.geteuid()+1):
            with self.assertRaisesRegex(OwnerIsolationUnavailable, "approval_storage_not_private"):
                require_isolated_approval_owner(self.sock, self.db)

    def test_reject_world_accessible_parent(self):
        os.chmod(self.dir, 0o755)
        with patch("klone.approval_owner_boundary_v22.kernel_peer_uid", return_value=os.geteuid()+1):
            with self.assertRaisesRegex(OwnerIsolationUnavailable, "approval_storage_not_private"):
                require_isolated_approval_owner(self.sock, self.db)

    def test_reject_database_symlink(self):
        link = self.dir / "link.sqlite3"
        try:
            link.symlink_to(self.db)
        except OSError:
            self.skipTest("symlink creation not available")
        with patch("klone.approval_owner_boundary_v22.kernel_peer_uid", return_value=os.geteuid()+1):
            with self.assertRaisesRegex(OwnerIsolationUnavailable, "approval_storage_not_private"):
                require_isolated_approval_owner(self.sock, link)

    def test_reject_relative_path(self):
        with patch("klone.approval_owner_boundary_v22.kernel_peer_uid", return_value=os.geteuid()+1):
            with self.assertRaisesRegex(OwnerIsolationUnavailable, "absolute_db_path_required"):
                require_isolated_approval_owner(self.sock, "relative.sqlite3")

    def test_reject_missing_db(self):
        with patch("klone.approval_owner_boundary_v22.kernel_peer_uid", return_value=os.geteuid()+1):
            with self.assertRaisesRegex(OwnerIsolationUnavailable, "approval_storage_unavailable"):
                require_isolated_approval_owner(self.sock, self.dir / "missing.sqlite3")

    def test_private_storage_with_mocked_distinct_uid_passes_preflight_only(self):
        # MOCK ONLY. This is not a successful real privilege-separation test.
        with patch("klone.approval_owner_boundary_v22.kernel_peer_uid", return_value=os.geteuid()+1):
            self.assertIsNone(require_isolated_approval_owner(self.sock, self.db))

    def test_no_approval_or_publish_api(self):
        import klone.approval_owner_boundary_v22 as m
        self.assertFalse(hasattr(m, "approve"))
        self.assertFalse(hasattr(m, "publish"))


if __name__ == "__main__":
    unittest.main()
