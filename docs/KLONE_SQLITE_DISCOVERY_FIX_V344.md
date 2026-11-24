# KLONE v3.4.4 – Unit test discovery duplication correction

2026-11-24. Parent: draft PR #208, commit `cb601ad15935a46798cc25b27d3e13cbe6945268`.

## Observed on Android / Termux

The prior operator-run full resource trace aborted with `error_code=test_count_does_not_match_requested_pin` (return code 2). The developer-specified expected count was **1611**, but real `unittest.discover("tests", pattern="test_*.py")` returned **1630**. The 19 extra cases were not new features: `tests/test_sqlite_fixture_closure_v343.py` exposed imported `StorageV23PosixTests` (19 `test_*` methods) at module scope, so `unittest` discovered them a second time.

## Test-only repair

Replace `from test_approval_storage_fd_v23 import StorageV23PosixTests, _SUPPORTED` with `import test_approval_storage_fd_v23 as storage_tests`. Access the original class and capability flag through that module object. A new assertion inside the existing fixture-closure regression requires **exactly one** test to be discoverable in its own test module. No test is added or removed semantically: original suite plus one connection-closure test should discover **1611** unique cases.

- Existing three test-only SQLite `closing(...)` fixes remain untouched.
- No production source, storage/approval logic, running database, service or role is changed.
- The original Termux verification script `scripts/klone-v343-termux-verify.sh` can be reused with the new exact commit: it expects one focused test and 1611 full-suite tests.
- Independently rerun `tools/trace_sqlite_full_v342.py` with the new commit and `--expect-count 1611` to test the old three warning sites. A clean result is not a proof that all possible resource leaks are absent.

## Why not change the expected count to 1630?

That would hide a real discovery bug, unnecessarily execute 19 tests twice, and weaken the meaning of the fixed test count. Removing the `TestCase` class re-export restores intended coverage.
