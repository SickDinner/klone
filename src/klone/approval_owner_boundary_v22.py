"""Fail-closed preflight for a future isolated Approval Service (LAB ONLY).

This is deliberately NOT a deployed IPC service. The service DB must belong
exclusively to the service OS identity, and the caller UID is obtained from the
kernel via AF_UNIX SO_PEERCRED -- never a JSON payload or actor claim.

On Termux, two terminal sessions have the same Android UID and are rejected.
No Python-level lock, 0600 file mode, or socket name can separate same-UID code.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import stat
import struct


class OwnerIsolationUnavailable(PermissionError):
    """No independent OS principal / protected private database is available."""


def kernel_peer_uid(conn: socket.socket) -> int:
    """Read kernel-supplied AF_UNIX credentials; fail closed everywhere else."""
    unix_family = getattr(socket, "AF_UNIX", None)
    if unix_family is None or not isinstance(conn, socket.socket) or conn.family != unix_family:
        raise OwnerIsolationUnavailable("unix_peer_credentials_required")
    if not hasattr(socket, "SO_PEERCRED"):
        raise OwnerIsolationUnavailable("peer_credentials_unsupported")
    try:
        size = struct.calcsize("3i")
        value = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
        pid, uid, gid = struct.unpack("3i", value)
        if pid <= 0 or uid < 0 or gid < 0:
            raise ValueError("invalid_credentials")
        return uid
    except (OSError, ValueError, TypeError, struct.error) as exc:
        raise OwnerIsolationUnavailable("peer_credentials_unavailable") from exc


def require_isolated_approval_owner(conn: socket.socket, db_path: str | Path) -> None:
    """Require separate OS identities + owned private DB and immediate parent.

    This is a *precondition*, NOT a permission grant or a sufficient security
    boundary. A future server still needs UID allowlisting, action/role/intent
    verification, source attestation, audit, and securely held secrets.
    """
    peer_uid = kernel_peer_uid(conn)
    if not hasattr(os, "geteuid"):
        raise OwnerIsolationUnavailable("service_uid_unsupported")
    owner_uid = os.geteuid()
    if peer_uid == owner_uid:
        raise OwnerIsolationUnavailable("same_uid_not_isolated")
    path = Path(db_path)
    # Prevent an attacker swapping a supplied symlink for the target file/dir.
    # An actual service must open via descriptor-relative O_NOFOLLOW and hold
    # the inode throughout use; lstat is only preflight, subject to TOCTOU.
    if not path.is_absolute() or not path.name or path.name in (".", ".."):
        raise OwnerIsolationUnavailable("absolute_db_path_required")
    try:
        db = path.lstat()
        parent = path.parent.lstat()
    except (OSError, ValueError) as exc:
        raise OwnerIsolationUnavailable("approval_storage_unavailable") from exc
    if (not stat.S_ISREG(db.st_mode) or not stat.S_ISDIR(parent.st_mode)
            or db.st_uid != owner_uid or parent.st_uid != owner_uid
            or (stat.S_IMODE(db.st_mode) & 0o077) != 0
            or (stat.S_IMODE(parent.st_mode) & 0o077) != 0):
        raise OwnerIsolationUnavailable("approval_storage_not_private")
    # Not an authorization decision: success only means the preflight checks
    # are satisfied, not that this requester is allowed to approve anything.
