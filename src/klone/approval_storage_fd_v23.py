"""Linux/Android descriptor-anchored SQLite storage inspection (LAB ONLY).

No database connection, writable authorization, IPC listener or migration.
This guards *inspection* against symlink-following and directory-path races.
It does not bind Python's sqlite3.connect(path) to the held file descriptor.
Only a separately sandboxed OS identity can protect storage from raw writers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import stat
from typing import Final


class StorageIsolationUnavailable(PermissionError):
    """The approval database cannot be inspected under the strict policy."""


_SIDE_SUFFIXES: Final = ("-wal", "-shm", "-journal")
_REQUIRED_FLAGS: Final = (
    "O_PATH", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK",
)


def _requirements() -> None:
    if (os.name != "posix" or not hasattr(os, "geteuid")
            or any(not hasattr(os, flag) for flag in _REQUIRED_FLAGS)
            or os.open not in getattr(os, "supports_dir_fd", ())
            or os.stat not in getattr(os, "supports_dir_fd", ())):
        raise StorageIsolationUnavailable("descriptor_api_unavailable")


def _parts(db_path: str | Path) -> tuple[str, ...]:
    # Check *original* spelling; Path() otherwise normalizes '.' segments.
    if not isinstance(db_path, (str, Path)):
        raise StorageIsolationUnavailable("absolute_db_path_required")
    raw = str(db_path)
    if (not raw.startswith("/") or len(raw) > 4096 or "\x00" in raw
            or raw.endswith("/") or "//" in raw):
        raise StorageIsolationUnavailable("absolute_db_path_required")
    parts = tuple(raw.split("/")[1:])
    if len(parts) < 2 or any(p in ("", ".", "..") for p in parts):
        raise StorageIsolationUnavailable("unsafe_path_component")
    return parts


def _directory(fd: int, *, uid: int, immediate: bool) -> None:
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        raise StorageIsolationUnavailable("not_a_directory")
    if immediate and (info.st_uid != uid or
                      stat.S_IMODE(info.st_mode) & 0o077 or
                      stat.S_IMODE(info.st_mode) & 0o700 != 0o700):
        raise StorageIsolationUnavailable("private_directory_required")
    if stat.S_IMODE(info.st_mode) & 0o022:
        # Writable ancestors permit pathname replacement by another identity.
        raise StorageIsolationUnavailable("writable_ancestor")


def _file(fd: int, *, uid: int) -> tuple[int, int]:
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
            or stat.S_IMODE(info.st_mode) & 0o077
            or stat.S_IMODE(info.st_mode) & 0o600 != 0o600
            or info.st_nlink != 1):
        raise StorageIsolationUnavailable("private_regular_file_required")
    return (info.st_dev, info.st_ino)


@dataclass
class VerifiedStorageSnapshot:
    """Owns an inspected directory fd and file fds; caller MUST close.

    This is diagnostic metadata, NOT a SQLite connection capability or
    authorization to approve. It cannot prevent privileged same-UID writes.
    """
    parent_fd: int
    database_fd: int
    database_name: str
    database_inode: tuple[int, int]
    sidecars: dict[str, tuple[int, tuple[int, int]]] = field(default_factory=dict)
    _closed: bool = field(default=False, init=False, repr=False)

    def check_names_unchanged(self) -> None:
        """Spot rebinding since the snapshot; not a lock or atomic guarantee."""
        if self._closed:
            raise StorageIsolationUnavailable("snapshot_closed")
        expected = {self.database_name: self.database_inode}
        expected.update({name: identity for name, (_, identity) in self.sidecars.items()})
        for name in (self.database_name,) + tuple(self.database_name + s for s in _SIDE_SUFFIXES):
            try:
                info = os.stat(name, dir_fd=self.parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                actual = None
            except OSError as exc:
                raise StorageIsolationUnavailable("storage_name_unavailable") from exc
            else:
                if not stat.S_ISREG(info.st_mode):
                    raise StorageIsolationUnavailable("storage_name_changed")
                actual = (info.st_dev, info.st_ino)
            if actual != expected.get(name):
                raise StorageIsolationUnavailable("storage_name_changed")

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            for fd in (self.database_fd, *(x[0] for x in self.sidecars.values()), self.parent_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def __enter__(self) -> "VerifiedStorageSnapshot":
        if self._closed:
            raise StorageIsolationUnavailable("snapshot_closed")
        return self

    def __exit__(self, _type, _value, _tb) -> None:
        self.close()


def _inspect_parts(parts: tuple[str, ...], *, trusted_root_fd: int | None) -> VerifiedStorageSnapshot:
    """Inspect below root or an explicitly trusted private directory fd."""
    _requirements()
    uid = os.geteuid()
    dir_flags = os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    parent_fd = -1
    db_fd = -1
    sidecars: dict[str, tuple[int, tuple[int, int]]] = {}
    transferred = False
    try:
        if trusted_root_fd is None:
            parent_fd = os.open("/", dir_flags)
            _directory(parent_fd, uid=uid, immediate=False)
        else:
            # Keep caller's capability alive; close only our owned duplicate.
            parent_fd = os.dup(trusted_root_fd)
            _directory(parent_fd, uid=uid, immediate=True)
        for segment in parts[:-1]:
            child = os.open(segment, dir_flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = child
            _directory(parent_fd, uid=uid, immediate=False)
        # The last opened directory is the database's direct parent. In the
        # loop all ancestors were checked for group/other write permissions.
        _directory(parent_fd, uid=uid, immediate=True)
        name = parts[-1]
        db_fd = os.open(name, file_flags, dir_fd=parent_fd)
        identity = _file(db_fd, uid=uid)
        for suffix in _SIDE_SUFFIXES:
            sibling = name + suffix
            try:
                fd = os.open(sibling, file_flags, dir_fd=parent_fd)
            except FileNotFoundError:
                continue
            try:
                sidecars[sibling] = (fd, _file(fd, uid=uid))
            except BaseException:
                os.close(fd)
                raise
        snapshot = VerifiedStorageSnapshot(parent_fd, db_fd, name, identity, sidecars)
        snapshot.check_names_unchanged()
        transferred = True
        return snapshot
    except StorageIsolationUnavailable:
        raise
    except (OSError, ValueError, OverflowError) as exc:
        raise StorageIsolationUnavailable("secure_storage_open_denied") from exc
    finally:
        # Ownership of opened descriptors passes to the snapshot on success.
        if not transferred:
            for fd in (db_fd, *(x[0] for x in sidecars.values()), parent_fd):
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass


def _relative_parts(relative_db_path: str | Path) -> tuple[str, ...]:
    """Only literal components below a caller-held trusted directory fd."""
    if not isinstance(relative_db_path, (str, Path)):
        raise StorageIsolationUnavailable("relative_db_path_required")
    raw = str(relative_db_path)
    if (not raw or raw.startswith("/") or len(raw) > 4096 or "\x00" in raw
            or raw.endswith("/") or "//" in raw):
        raise StorageIsolationUnavailable("relative_db_path_required")
    parts = tuple(raw.split("/"))
    if any(p in ("", ".", "..") for p in parts):
        raise StorageIsolationUnavailable("unsafe_path_component")
    return parts


def inspect_private_approval_storage(db_path: str | Path) -> VerifiedStorageSnapshot:
    """Strict absolute-path walker; refuses writable ancestors from filesystem root.

    No special case is made for Android's system-managed /data ancestors.
    Use the capability-anchored variant with a trusted private directory fd
    when the root-to-home path cannot satisfy this conservative policy.
    """
    _requirements()
    return _inspect_parts(_parts(db_path), trusted_root_fd=None)


def inspect_private_approval_storage_at(
    trusted_root_fd: int, relative_db_path: str | Path,
) -> VerifiedStorageSnapshot:
    """Inspect a DB relative to an independently provisioned *trusted* dirfd.

    The trusted host must obtain/protect this directory capability itself,
    never accept an fd from an untrusted client. The fd must identify a private
    directory owned by the effective service UID. Symlink, writable nested
    ancestor, database and SQLite sidecar checks remain fail-closed.

    A verified snapshot does not grant authorization, prevent same-UID writes,
    or bind sqlite3.connect(path) to the inspected fd.
    """
    _requirements()
    if type(trusted_root_fd) is not int or trusted_root_fd < 0:
        raise StorageIsolationUnavailable("trusted_root_fd_required")
    parts = _relative_parts(relative_db_path)
    return _inspect_parts(parts, trusted_root_fd=trusted_root_fd)
