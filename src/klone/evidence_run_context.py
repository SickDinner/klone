"""Versioned execution context claims for new evidence runs; no attestation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from klone.evidence_io import checked_path, read_bounded

MAX_FILES = 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_TREE_BYTES = 16 * 1024 * 1024
STAGES = ("syntax", "cognition", "full", "local_deploy", "torch_probe")
HEX = re.compile(r"[0-9a-f]{64}")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def tree_files(directory: Path, *, python_only: bool = False) -> list[Path]:
    checked_path(directory, directory=True)
    result, entries = [], 0
    for parent, directories, files in os.walk(directory, followlinks=False):
        for name in [*directories, *files]:
            entries += 1
            if entries > 4096:
                raise ValueError("source tree entry limit")
            checked_path(Path(parent) / name)
        directories[:] = sorted(d for d in directories if d != "__pycache__")
        result.extend(Path(parent) / f for f in sorted(files)
                      if (not python_only or f.endswith(".py")) and not f.endswith((".pyc", ".pyo")))
        if len(result) > MAX_FILES:
            raise ValueError("Python file count limit")
    return sorted(result)


def suite_snapshot(root: Path) -> dict:
    root = checked_path(root, directory=True)
    paths = tree_files(root / "tests")
    for name in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", "conftest.py"):
        path = root / name
        checked_path(path)
        if path.exists():
            paths.append(path)
    records, consumed = [], 0
    for path in sorted(paths):
        raw = read_bounded(path, min(MAX_FILE_BYTES, MAX_TREE_BYTES - consumed))
        consumed += len(raw)
        records.append({"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
    if not records:
        raise ValueError("test suite is empty")
    return {"sha256": digest(records), "file_count": len(records)}


def syntax_check(source: Path) -> dict:
    errors, consumed, count = [], 0, 0
    for path in tree_files(source, python_only=True):
        raw = read_bounded(path, min(MAX_FILE_BYTES, MAX_TREE_BYTES - consumed))
        consumed += len(raw)
        count += 1
        try:
            compile(raw, str(path), "exec", dont_inherit=True)
        except SyntaxError as exc:
            errors.append({"file": path.relative_to(source).as_posix(),
                           "line": exc.lineno, "reason": str(exc.msg)[:256]})
    return {"schema_version": 1, "kind": "klone-syntax-check", "files": count,
            "status": "failed" if errors or not count else "passed", "errors": errors}


def validate_environment(environment: dict) -> None:
    keys = {"python_version", "implementation", "platform", "machine", "system_release", "sysconfig_platform", "packages"}
    if not isinstance(environment, dict) or set(environment) != keys:
        raise ValueError("invalid environment fields")
    for key in keys - {"packages"}:
        value = environment[key]
        if not isinstance(value, str) or not 1 <= len(value) <= 256:
            raise ValueError("invalid environment string")
    packages = environment["packages"]
    if not isinstance(packages, dict) or len(packages) > 1024:
        raise ValueError("invalid installed package map")
    if any(not isinstance(k, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,99}", k)
           or not isinstance(v, str) or not 1 <= len(v) <= 100 for k, v in packages.items()):
        raise ValueError("invalid installed package metadata")


def context_id(environment: dict, execution: dict) -> str:
    return digest({"context_version": 1, "environment": environment,
                   "commands": {name: ["$PYTHON", *args[1:]] if args else None
                                for name, args in execution["commands"].items()},
                   "test_suite": execution["test_suite_before"],
                   "collector_sha256": execution["collector_sha256"],
                   "timeout_seconds": execution["timeout_seconds"],
                   "environment_overrides": {k: "$ROOT/src" if k == "PYTHONPATH" else v
                                             for k, v in execution["environment_overrides"].items()}})


def validate_context(run: dict) -> dict:
    environment, execution = run.get("environment"), run.get("execution")
    validate_environment(environment)
    if not isinstance(execution, dict) or type(execution.get("context_version")) is not int or execution["context_version"] != 1:
        raise ValueError("invalid execution context version")
    for key in ("cwd", "python_executable", "python_prefix"):
        if not isinstance(execution.get(key), str) or not 1 <= len(execution[key]) <= 4096:
            raise ValueError("missing execution path")
    if execution.get("virtualenv_reported") is not True:
        raise ValueError("selected interpreter is not a reported virtualenv")
    commands = execution.get("commands")
    if not isinstance(commands, dict) or set(commands) != set(STAGES):
        raise ValueError("invalid execution command set")
    for name, args in commands.items():
        if args is None and name == "torch_probe":
            continue
        if (not isinstance(args, list) or not 2 <= len(args) <= 32
                or any(not isinstance(a, str) or not 1 <= len(a) <= 4096 or "\x00" in a for a in args)
                or args[0] != execution["python_executable"]):
            raise ValueError("invalid exact command arguments")
    overrides = execution.get("environment_overrides")
    # Recorded Android paths must also validate when analyzed on Windows.
    path_type = PureWindowsPath if "\\" in execution["cwd"] or re.match(r"^[a-zA-Z]:", execution["cwd"]) else PurePosixPath
    if overrides != {"PYTHONPATH": str(path_type(execution["cwd"]) / "src"),
                     "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}:
        raise ValueError("unsupported execution environment overrides")
    if type(execution.get("timeout_seconds")) is not int or not 1 <= execution["timeout_seconds"] <= 3600:
        raise ValueError("invalid execution timeout")
    for key in ("collector_sha256", "collector_after_sha256", "environment_after_sha256", "comparison_id"):
        if not isinstance(execution.get(key), str) or not HEX.fullmatch(execution[key]):
            raise ValueError("invalid execution digest")
    for key in ("test_suite_before", "test_suite_after"):
        suite = execution.get(key)
        if (not isinstance(suite, dict) or set(suite) != {"sha256", "file_count"}
                or not isinstance(suite["sha256"], str) or not HEX.fullmatch(suite["sha256"])
                or type(suite["file_count"]) is not int or not 1 <= suite["file_count"] <= MAX_FILES + 5):
            raise ValueError("invalid test suite fingerprint")
    consistent = (execution["collector_sha256"] == execution["collector_after_sha256"]
                  and execution["environment_after_sha256"] == digest(environment)
                  and execution["test_suite_before"] == execution["test_suite_after"])
    if execution.get("context_consistent") is not consistent:
        raise ValueError("contradictory execution context claim")
    if execution["comparison_id"] != context_id(environment, execution):
        raise ValueError("execution context digest mismatch")
    stages = run.get("stages", {})
    for name in STAGES:
        stage = stages.get(name)
        if not isinstance(stage, dict) or type(stage.get("capture_complete")) is not bool:
            raise ValueError("missing capture completeness")
        if commands[name] is not None and type(stage.get("exit_code")) is not int:
            raise ValueError("missing process exit code")
        if (commands[name] is None) != (stage.get("status") == "not_present"):
            raise ValueError("command and optional-stage absence mismatch")
    complete = all(stages[n]["capture_complete"] for n in STAGES)
    if run.get("collection_complete") is not complete:
        raise ValueError("contradictory collection completeness")
    return execution


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["syntax"])
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = syntax_check(args.source)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
