# KLONE v3.4.2 — Full-suite SQLite resource trace (LAB)

Base: PR #206 commit `a7a562067133c6fdac647db8cc76e9e4bdb4d74a`.

The previous `tools/trace_sqlite_resources_v341.py` intentionally tests **20 selected modules**. Android ran three disjoint groups: memory 39 tests, research 15 tests, and approval 66 tests. All 120 selected tests passed with no captured ResourceWarnings. This does **not** explain the historical unclosed-SQLite warnings during a broader suite.

The v3.4.2 runner `tools/trace_sqlite_full_v342.py`:

- Runs all `test_*.py` files from `tests/` **in one Python process**. No `--group all` ambiguity.
- Requires an exact checked-out Git commit SHA before loading tests; optional `--expect-count N` refuses an unexpected discovery count rather than silently claiming complete coverage. The count is determined from the current checkout, not embedded in the runner.
- Enables `tracemalloc`, captures `ResourceWarning` events from import/discovery through test execution and two explicit GC passes, and reports sanitized file/line allocation frames when Python makes them available.
- Suppresses raw unittest stdout, stderr, traceback bodies and test fixture values from machine-readable JSON output. Test failures appear as **counts only**; reproduce them with the usual `unittest` runner to view full detail in your local context.
- Produces a reproducible digest and explicit **unauthenticated** data-source limitation. Digest is not a signature, independent provenance anchor or approval.
- Returns `0` for an apparently clean successful test run, `2` for regression/coverage/launch errors, and `3` if any ResourceWarnings are captured (even if the tests pass).

Test processes may perform writes to their own temporary fixtures. Before executing on an unfamiliar checkout, inspect the tests. The tracer itself does not select a production database or manipulate live services. It cannot catch all warnings from subprocesses, handles deliberately held alive past the end of the run, or warnings emitted after interpreter shutdown. A zero warning count **is not proof of no resource leak**.

## Termux

From the new pinned v3.4.2 detached worktree:

```sh
PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 \
  "$HOME/klone-next/.venv/bin/python" \
  tools/trace_sqlite_full_v342.py \
  --expected-commit "$EXPECTED" --expect-count "$COUNT" \
  --trace-frames 15
```

`COUNT` is optional; use the exact total for v3.4.2 only after the checkout has been verified. Run from a separate shell so the live API 8000 and Mission Control 8011 are not disturbed. The resource trace can consume substantially more CPU, memory and time than regular unit tests on Android; do not run it with low battery or during a heavy device workload.

If captured SQLite warnings identify a source line, reproduce the narrow test before changing connection management. Do not edit the production DB or reuse an unsigned local report as permission to act.
