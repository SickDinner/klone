# KLONE Approval Storage FD v2.3 — experimental defense-in-depth

**LAB ONLY. No real approval service, database migration, or production IPC.**

## Purpose

On PR #191, `require_isolated_approval_owner` uses `lstat` on a pathname. A
pathname can be redirected between inspection and opening (TOCTOU). This new
module implements a *descriptor-anchored inspection* of the approval database.
It is a distinct design experiment, not a replacement for OS sandbox isolation.

`inspect_private_approval_storage(absolute_db_path)`:

- Requires POSIX `O_PATH`, `O_DIRECTORY`, `O_NOFOLLOW`, `O_CLOEXEC`, `dir_fd`
  support and a real effective UID. All unsupported platforms deny by default.
- Walks from `/`, opening each directory relative to the preceding held fd with
  `O_NOFOLLOW` and checking for group/other-writable ancestors.
- Requires the immediate database directory to be service-owned and 0700-like.
  Requires the DB to be a service-owned 0600-like regular file with one link.
- Inspects **all existing** `-wal`, `-shm` and `-journal` companions using the
  same parent dirfd, without following links, and checks their type/ownership/mode.
- Keeps all inspected directory/file handles alive until the caller closes the
  context. `check_names_unchanged()` catches name-to-inode replacement or newly
  created companion files after the inspection snapshot. The check is **not a
  filesystem lock**; a write-capable attacker can rebind names again afterward.
- Does not load signing keys, run SQLite, publish content, call models, create
  a privileged server, or authorize approval.

## Critical limitation

Python `sqlite3.connect(path)` opens by a pathname. **This implementation does
not bind SQLite's open to an already verified descriptor.** Treating this
snapshot as an authorization or guaranteeing no pathname race would be a false
security claim. SQLite can create or replace WAL/SHM/journal companions after
inspection. A real service needs protected private storage owned by a *different
OS principal* and a reviewed opening strategy that keeps SQLite and its
sidecar file operations confined to that private namespace. Linux-specific
procfd/URI tricks must not be assumed safe without SQLite VFS analysis.

Android Termux sessions normally share one UID. Neither `O_NOFOLLOW` nor 0600
permissions prevent a malicious same-UID process from writing the DB. PR #191's
separate-UID preflight remains necessary but is not sufficient; real separate
Android app sandbox/permissions/authorized IPC need additional development.

## Testing

`PYTHONPATH=src python -m unittest discover -s tests -p 'test_approval_storage_fd_v23.py' -v`

Linux/Android tests use per-test temporary storage in the canonicalized home
directory (`Path.home().resolve(strict=True)`), to account for Android
`/data/data` being a system-level symlink on some devices. Arbitrary
requester-supplied symlink paths are still denied by the secure walker.
Windows runs only portable fail-closed checks and skips POSIX-only tests. No
existing KLONE database is opened or modified. One red-team test deliberately shows a same-UID raw SQLite writer can UPDATE
a table while verified descriptors are held: **the snapshot is not an access
control boundary**. Another test deliberately simulates
an owner replacement of the pathname *after* inspection, proving that a held fd
preserves the prior inode while a subsequent path-based open could differ.

## Next gates

1. Run tests on Android/Termux, Linux CI and Windows CI.
2. Complete full `test_*.py` regression on the new commit.
3. Review trusted writer identity and an OS-managed privileged IPC boundary.
4. Add property-based/fuzz testing for unsafe paths and mixed sidecar states,
   measured on actual relevant platforms, without claiming production safety.

## Termux regression fix: explicit trusted-root directory capability

The initial Android run failed eight test cases and one assertion because
an absolute-path inspection starts at `/`, where Android's system-managed
`/data` ancestor may be group-writable (not writable by the Termux app UID).
We deliberately **did not waive the ancestor permissions check** in the
absolute-path walker.

`inspect_private_approval_storage_at(trusted_root_fd, relative_db_path)`
accepts an already-open, service-owned, mode-0700 private directory fd from the
**trusted service host**. It refuses relative `..`, symlinks, public/nested
writable directories, weak database and sidecar permissions; it checks each
object using descriptor-relative operations. Caller retains ownership of the
original fd. Never pass an untrusted client-supplied fd or treat the snapshot
as authority to connect SQLite. Its security assumption is that the service
host obtained the directory capability from OS-managed app-private storage;
this lab does not independently attest Android's parent chain or its SELinux
policy.

The test fixture uses its own new temporary directory fd instead of scanning
the entire Android `/data` chain. The `os.link` hardlink test is skipped only
on Python builds lacking that API; `_file()` still denies files having more
than one hardlink. Linux CI retains that test.
