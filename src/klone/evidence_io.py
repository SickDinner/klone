"""Bounded evidence I/O. Never follow links or publish into source evidence.

POSIX directory descriptors pin path components during file reads and report
publication. The portable fallback checks component identities before/after
opening. Neither mode authenticates historical provenance.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid


class EvidenceIOError(ValueError):
    def __init__(self, code: str, size: int | None = None):
        super().__init__(code)
        self.code, self.size = code, size


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def checked_path(path: Path, *, directory: bool = False) -> Path:
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            if directory:
                raise EvidenceIOError("missing")
            continue
        if _linked(info):
            raise EvidenceIOError("symlink_rejected")
    if directory and not path.is_dir():
        raise EvidenceIOError("not_directory")
    return path


_DIR_FD = os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW")


@contextmanager
def directory_handle(path: Path, *, create: bool = False):
    path = checked_path(path)
    if not _DIR_FD:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        checked_path(path, directory=True)
        yield None
        checked_path(path, directory=True)
        return
    try:
        descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    except PermissionError:
        # Android app sandboxes can traverse their private directory while
        # disallowing opening '/'. Keep O_NOFOLLOW on the final component.
        checked_path(path, directory=True)
        yield None
        checked_path(path, directory=True)
        return
    try:
        for name in path.parts[1:]:
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            next_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
        yield descriptor
    finally:
        os.close(descriptor)


def read_bounded(path: Path, limit: int) -> bytes:
    if type(limit) is not int or limit < 0:
        raise ValueError("invalid byte limit")
    path = checked_path(path)
    try:
        before = path.lstat()
        if _linked(before):
            raise EvidenceIOError("symlink_rejected")
        if not stat.S_ISREG(before.st_mode):
            raise EvidenceIOError("not_regular")
        if before.st_size > limit:
            raise EvidenceIOError("oversized", before.st_size)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        with directory_handle(path.parent) as parent_fd:
            descriptor = (os.open(path.name, flags | os.O_NOFOLLOW, dir_fd=parent_fd)
                          if parent_fd is not None else os.open(path, flags | os.O_NOFOLLOW))
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                if (not stat.S_ISREG(opened.st_mode)
                        or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                    raise EvidenceIOError("changed_during_read")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
        if len(raw) > limit:
            raise EvidenceIOError("oversized", len(raw))
        final = path.lstat()
        if (_linked(final) or (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino)
                or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                or len(raw) != after.st_size):
            raise EvidenceIOError("changed_during_read")
        checked_path(path)
        return raw
    except FileNotFoundError as exc:
        raise EvidenceIOError("missing") from exc
    except OSError as exc:
        raise EvidenceIOError("unreadable") from exc


def json_object(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("non-finite JSON number")

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def output_path(path: Path, source_root: Path) -> Path:
    source = checked_path(source_root, directory=True)
    target = checked_path(path)
    if target == source or target.is_relative_to(source):
        raise ValueError("report output must be outside source evidence")
    if target.exists() and not target.is_file():
        raise ValueError("report output must be a regular file")
    return target


def write_report(path: Path, content: str, source_root: Path) -> None:
    """Atomically replace only an explicitly selected report outside source_root."""
    target = output_path(path, source_root)
    raw = content.encode("utf-8")
    if _DIR_FD:
        # Android may deny opening '/', so use the portable atomic writer
        # when directory-descriptor traversal is unavailable.
        try:
            anchor_fd = os.open(target.anchor, os.O_RDONLY | os.O_DIRECTORY)
        except PermissionError:
            anchor_fd = None
        if anchor_fd is not None:
            os.close(anchor_fd)
        if anchor_fd is None:
            _write_report_portable(target, raw, source_root)
            return
        with directory_handle(target.parent, create=True) as parent_fd:
            temporary = ".klone-report-" + uuid.uuid4().hex
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(raw)
                output_path(target, source_root)
                os.replace(temporary, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
    else:
        _write_report_portable(target, raw, source_root)


def _write_report_portable(target: Path, raw: bytes, source_root: Path) -> None:
    """Atomic fallback when Android blocks opening the filesystem anchor."""
    target.parent.mkdir(parents=True, exist_ok=True)
    output_path(target, source_root)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            name = handle.name
            handle.write(raw)
        output_path(target, source_root)
        os.replace(name, target)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)
