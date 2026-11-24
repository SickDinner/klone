"""KLONE v3.4.2: exact-commit full-suite SQLite ResourceWarning attribution (LAB).

Run only on a reviewed checkout, with explicit operator consent. This executes
existing tests and their normal temporary fixtures; it does not open a named
production DB, restart a service, or create a persistent daemon. The report is
local-only, unsigned and does not prove the absence of a connection leak.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import gc
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import tracemalloc
import unittest
import warnings

from trace_sqlite_resources_v341 import assert_exact_checkout, summarize_warnings

ROOT = Path(__file__).resolve().parents[1]
MAX_TESTS = 10000
MIN_TESTS = 1
MAX_FRAMES = 25


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def validate_expected_count(expected_count: int | None) -> None:
    if expected_count is not None and (
        type(expected_count) is not int or not MIN_TESTS <= expected_count <= MAX_TESTS
    ):
        raise ValueError("invalid_expected_test_count")


def _test_summary(result: unittest.TestResult, n: int) -> dict:
    return {
        "test_count": n,
        "tests_ran": result.testsRun,
        "tests_successful": result.wasSuccessful(),
        "tests_skipped": len(result.skipped),
        "test_failure_count": len(result.failures),
        "test_error_count": len(result.errors),
        "tests_passed": max(0, result.testsRun - len(result.failures) -
                            len(result.errors) - len(result.skipped)),
    }


def run_full_trace(*, expected_sha: str, expected_count: int | None = None,
                   max_frames: int = 15, _loader=None, _runner=None,
                   _checkout_validator=None) -> dict:
    """Run *all* test_*.py in one process, capturing warnings through GC.

    `_loader`, `_runner` and `_checkout_validator` are test-only injection
    seams, never CLI parameters. No untrusted filename or URL selector exists.
    """
    validate_expected_count(expected_count)
    if type(max_frames) is not int or not 5 <= max_frames <= MAX_FRAMES:
        raise ValueError("invalid_trace_frames")
    if _checkout_validator is None:
        assert_exact_checkout(ROOT, expected_sha)
    else:
        _checkout_validator(ROOT, expected_sha)
    tests_root = ROOT / "tests"
    if not tests_root.is_dir():
        raise ValueError("tests_directory_missing")
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    # Existing Termux test venv can use system cryptography for tests, without
    # modifying pip packages or the active API process. This remains a caveat
    # in test reproducibility rather than a production installation model.
    system_site = (Path(sys.base_prefix) / "lib" /
                   f"python{sys.version_info.major}.{sys.version_info.minor}" /
                   "site-packages")
    if system_site.is_dir() and str(system_site) not in sys.path:
        sys.path.append(str(system_site))
    loader = unittest.defaultTestLoader if _loader is None else _loader
    tracer_started_here = not tracemalloc.is_tracing()
    if tracer_started_here:
        tracemalloc.start(max_frames)
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", ResourceWarning)
            # Some imported tests print to stdout/stderr during discovery.
            # Keep their untrusted output off the machine-readable JSON stream.
            with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
                with redirect_stdout(output), redirect_stderr(output):
                    suite = loader.discover(str(tests_root), pattern="test_*.py")
                    test_count = suite.countTestCases()
                    if not MIN_TESTS <= test_count <= MAX_TESTS:
                        raise ValueError("discovered_test_count_out_of_bounds")
                    if expected_count is not None and test_count != expected_count:
                        raise ValueError("test_count_does_not_match_requested_pin")
                    runner = (unittest.TextTestRunner(stream=output, verbosity=1)
                              if _runner is None else _runner)
                    result = runner.run(suite)
                    # unittest ordinarily clears successful suite references.
                    # Explicitly release the suite before collection to catch
                    # connections that become unreachable only after tests.
                    del suite
                    gc.collect()
                    gc.collect()
                # Deliberately do not export raw test stdout or exceptions:
                # they can contain private fixture data and local DB paths.
            warnings_report = summarize_warnings(captured, max_frames=max_frames,
                                                 max_items=25)
        report = {
            "schema_version": 1,
            "kind": "klone-sqlite-full-trace-v342-lab",
            "suite_scope": "all_repository_test_py_modules",
            "source_commit_sha_claim": expected_sha,
            "test_loader_pattern": "test_*.py",
            "expected_test_count": expected_count,
            "test_count_pin_matched": (expected_count is not None and
                                       test_count == expected_count),
            "trace_frames": max_frames,
            **_test_summary(result, test_count),
            **warnings_report,
            "test_output_exported": False,
            "subprocess_resource_warnings_in_scope": False,
            "warnings_after_process_exit_in_scope": False,
            "source_origin_authenticated": False,
            "production_database_selected_by_tracer": False,
            "database_migration_performed_by_tracer": False,
            "service_restart_performed_by_tracer": False,
            "approval_granted": False,
            "warning_absence_proves_no_leak": False,
        }
        report["report_sha256"] = sha256(
            b"klone-v342-local-sqlite-trace\x00" + _canonical(report)
        ).hexdigest()
        return report
    finally:
        if tracer_started_here:
            tracemalloc.stop()


def report_exit_code(report: dict) -> int:
    """2: regression/coverage failure; 3: captured warning; 0: clean run."""
    if not report["tests_successful"] or report["tests_ran"] != report["test_count"]:
        return 2
    if report["resource_warning_count"]:
        return 3
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expect-count", type=int)
    parser.add_argument("--trace-frames", type=int, default=15)
    args = parser.parse_args(argv)
    try:
        report = run_full_trace(expected_sha=args.expected_commit,
                                expected_count=args.expect_count,
                                max_frames=args.trace_frames)
    except (ValueError, OSError) as exc:
        # No raw exception text in output; common errors are known fixed codes.
        code = str(exc)
        if code not in {"invalid_expected_test_count", "invalid_trace_frames",
                        "tests_directory_missing", "discovered_test_count_out_of_bounds",
                        "test_count_does_not_match_requested_pin",
                        "invalid_expected_commit", "checkout_commit_mismatch"}:
            code = "trace_setup_or_test_discovery_error"
        print(json.dumps({"kind": "klone-sqlite-full-trace-v342-error",
                          "error_code": code, "approval_granted": False},
                         sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return report_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
