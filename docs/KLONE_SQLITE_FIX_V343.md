# KLONE v3.4.3 – Close three SQLite red-team test connections

2026-11-24. Parent: v3.4.2 draft PR #207 at `dc2abadcced980d8bbcf98d47d56ba3e8828a37c`.

## Actual Android evidence

The user ran 1596 v3.4.1 test cases in one process on Python 3.13 with ResourceWarning capture and tracemalloc. All passed (2 skipped), but exactly **three unclosed SQLite connections** were reported. The allocation frames pointed directly to `tests/test_approval_storage_fd_v23.py` lines **209, 214, 216**, all in one method: `test_snapshot_does_not_prevent_same_uid_raw_sqlite_update`.

The Pydantic line 73 cited in the warning was the collection/emission site, not a connection allocation site.

## Root cause and fix

Python's `with sqlite3.connect(...)` manages transaction commit/rollback, **not connection closure**. Test fixture code created 3 connections without `close()`. Each is now nested in `contextlib.closing` *outside* its transaction context:

```python
with closing(sqlite3.connect(self.db)) as db, db:
    ...
```

The inner `db` context commits/rolls back before the outer `closing` context closes. The red-team claim (same UID can bypass read-only fd inspection and directly write SQLite) remains unchanged. The following existing WAL+SHM test already uses `finally: con.close()`.

A new regression re-executes that exact red-team fixture with a tracked `sqlite3.Connection` subclass; it requires three observed connections and asserts each receives exactly one `close()` and rejects subsequent queries. It is skipped where the underlying POSIX fd-inspection fixture is unavailable.

**Scope:** test fixture only. No production database, application code, API, service, storage policy, approval grant, or migration is changed.

## Verification

From the exact v3.4.3 detached worktree on Android:

```sh
bash scripts/klone-v343-termux-verify.sh <40-character-commit>
```

This checks the precise commit, focused closure regression and full `unittest` suite. The full suite is expected to discover **1611** tests after adding one regression to the v3.4.2's 1610.

For final resource confirmation, manually run the inherited `tools/trace_sqlite_full_v342.py` with `--expected-commit <same-commit> --expect-count 1611`. It can be CPU/memory intensive on Android. It catches in-process warnings visible through the two explicit GC passes but cannot prove the absence of all possible leaks. Re-run the full tracer if a ResourceWarning returns; preserve the allocation frames.

No PR merge or production approval occurs in this change.
