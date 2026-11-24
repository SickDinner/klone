"""Bounded, opt-in sqlite3 ResourceWarning attribution for KLONE test fixtures.

LAB ONLY: no live DB selectors, process control, network, or production changes.
The script does run existing tests, which may write to their isolated fixtures.
A missing warning is NOT proof that no resource leak exists.
"""
from __future__ import annotations

import argparse
import gc
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tracemalloc
import unittest
import warnings

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "memory": (
        "test_memory_phase_2b2.py", "test_memory_phase_2b3.py",
        "test_memory_phase_2b5.py", "test_memory_phase_2c1.py",
        "test_memory_phase_2c1_provenance.py", "test_memory_phase_2c2.py",
        "test_memory_phase_2c3.py", "test_memory_phase_2c4.py",
        "test_memory_phase_2c5.py", "test_cognition_memory.py",
    ),
    "research": (
        "test_research_memory.py", "test_research_audit_outbox.py",
        "test_research_audit_consistency.py", "test_research_source_audit.py",
        "test_mission_control_status_ui.py",
    ),
    "approval": (
        "test_approval_checkpoint_v25.py", "test_approval_gateway.py",
        "test_approval_journal.py", "test_evidence_approval_bridge_sqlite.py",
        "test_approval_atomic_gateway.py",
    ),
}


def source_patterns(group: str) -> tuple[str, ...]:
    """Fixed local test patterns, never caller-supplied paths or SQL."""
    if group == "all":
        return tuple(dict.fromkeys(p for entries in GROUPS.values() for p in entries))
    if group not in GROUPS:
        raise ValueError("unsupported_trace_group")
    return GROUPS[group]


def assert_exact_checkout(root: Path, expected_sha: str) -> None:
    if type(expected_sha) is not str or SHA40.fullmatch(expected_sha) is None:
        raise ValueError("invalid_expected_commit")
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                               check=True, capture_output=True, text=True)
    if completed.stdout.strip() != expected_sha:
        raise ValueError("checkout_commit_mismatch")


def _classify(message: object) -> str:
    text = str(message).lower()
    if "unclosed database" in text or "sqlite3.connection" in text:
        return "sqlite_connection_unclosed"
    return "other_resource_warning"


def resource_warning_summary(warning: warnings.WarningMessage, *, max_frames: int) -> dict:
    """Never emit warning message text (could carry SQL or sensitive paths)."""
    if type(max_frames) is not int or not 1 <= max_frames <= 30:
        raise ValueError("invalid_frame_limit")
    kind = _classify(warning.message)
    result = {"kind": kind,
              "emitted_from": {"file": str(warning.filename), "line": int(warning.lineno)},
              "allocation_trace_available": False, "allocation_frames": []}
    source = getattr(warning, "source", None)
    if source is not None and tracemalloc.is_tracing():
        try:
            trace = tracemalloc.get_object_traceback(source)
        except (TypeError, ValueError):
            trace = None
        if trace is not None:
            result["allocation_trace_available"] = True
            result["allocation_frames"] = [
                {"file": str(frame.filename), "line": int(frame.lineno)}
                for frame in list(trace)[-max_frames:]
            ]
    return result


def summarize_warnings(messages, *, max_frames: int = 15, max_items: int = 25) -> dict:
    if type(max_items) is not int or not 1 <= max_items <= 100:
        raise ValueError("invalid_warning_limit")
    filtered = [m for m in messages if isinstance(m.message, ResourceWarning)]
    summaries = [resource_warning_summary(m, max_frames=max_frames)
                 for m in filtered[:max_items]]
    sqlite_count = sum(_classify(m.message) == "sqlite_connection_unclosed"
                       for m in filtered)
    return {"resource_warning_count": len(filtered),
            "sqlite_connection_warning_count": sqlite_count,
            "warning_output_truncated": len(filtered) > max_items,
            "warnings": summaries,
            "warning_absence_proves_no_leak": False}


def run_group(*, group: str, expected_sha: str, max_frames: int = 15) -> dict:
    """Run bounded, selected suites with ResourceWarnings captured and GC forced.

    This script must run as its own process for each group, so retained test
    objects and warning message sources cannot influence a subsequent group.
    """
    assert_exact_checkout(ROOT, expected_sha)
    patterns = source_patterns(group)
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        raise ValueError("tests_directory_missing")
    for pattern in patterns:
        if not (tests_dir / pattern).is_file():
            raise ValueError("test_module_missing:" + pattern)
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    # Termux: an existing system cryptography package can supply the test-only
    # dependency if it isn't installed in the separate venv. No pip operation.
    site = (Path(sys.base_prefix) / "lib" /
            f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages")
    if site.is_dir() and str(site) not in sys.path:
        sys.path.append(str(site))
    tracemalloc.start(max_frames)
    # Prevent warning text from being printed into the report. Only the file,
    # line and (when provided) allocation trace are exposed.
    with warnings.catch_warnings(record=True) as collected:
        warnings.simplefilter("always", ResourceWarning)
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for pattern in patterns:
            suite.addTests(loader.discover(str(tests_dir), pattern=pattern))
        count = suite.countTestCases()
        if count == 0:
            raise ValueError("no_tests_discovered")
        # Keep actual unittest failures in a local bounded output, not in the
        # JSON digest; avoid leaking raw assertion or local DB values.
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
        gc.collect()
        gc.collect()
        warning_report = summarize_warnings(collected, max_frames=max_frames)
    report = {"kind": "klone-sqlite-resource-trace-v341-lab",
              "group": group, "tested_module_count": len(patterns),
              "test_count": count, "tests_successful": result.wasSuccessful(),
              "tests_skipped": len(result.skipped),
              "test_failure_count": len(result.failures),
              "test_error_count": len(result.errors),
              **warning_report,
              "source_origin_authenticated": False,
              "production_database_opened_by_tracer": False,
              "database_migration_performed": False,
              "memory_write_authorized": False,
              "approval_granted": False}
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--group", choices=(*GROUPS.keys(), "all"), required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--trace-frames", type=int, default=15)
    args = p.parse_args(argv)
    if not 5 <= args.trace_frames <= 25:
        p.error("trace frames must be between 5 and 25")
    try:
        report = run_group(group=args.group, expected_sha=args.expected_commit,
                           max_frames=args.trace_frames)
    except (ValueError, subprocess.CalledProcessError) as exc:
        p.error(str(exc))
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True), flush=True)
    if not report["tests_successful"]:
        return 2
    if report["resource_warning_count"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
