"""Offline battery v2: exact commands, context claims and new-run-only evidence.

Never installs dependencies, changes git branches, signs evidence or starts a
service. Test code is executed only by an explicit invocation of this collector.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klone.evidence_io import checked_path, directory_handle, json_object, read_bounded
from klone.evidence_network import MAX_LOG, assemble_packet, canonical, validate_run
from klone.evidence_run_context import context_id, digest, suite_snapshot, validate_environment

PROBE = r'''
import importlib.metadata as metadata
import json, platform, re, sys, sysconfig
packages = {}
for distribution in metadata.distributions():
    name = re.sub(r"[-_.]+", "-", distribution.metadata.get("Name", "")).lower()
    version = distribution.version
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", name) or not 1 <= len(version) <= 100:
        raise ValueError("invalid installed package metadata")
    if name in packages and packages[name] != version:
        raise ValueError("conflicting installed distribution versions")
    packages[name] = version
    if len(packages) > 1024:
        raise ValueError("installed distribution limit")
environment = dict(python_version=platform.python_version(), implementation=platform.python_implementation(),
                   platform=sys.platform, machine=platform.machine() or "unknown",
                   system_release=platform.release() or "unknown", sysconfig_platform=sysconfig.get_platform(),
                   packages=packages)
result = dict(environment=environment, executable=sys.executable, prefix=sys.prefix,
              virtualenv_reported=sys.prefix != sys.base_prefix)
raw = json.dumps(result, sort_keys=True)
if len(raw.encode()) > 32768:
    raise ValueError("environment metadata limit")
print(raw)
'''


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def checkout(root: Path) -> dict:
    return {"commit": git(root, "rev-parse", "HEAD"),
            "branch": git(root, "branch", "--show-current"),
            "dirty": bool(git(root, "status", "--porcelain"))}


def validate_destination(root: Path, output: Path) -> None:
    checked_path(output)
    if output == root or output.is_relative_to(root) or ".git" in output.parts:
        raise ValueError("run output must be outside the tested checkout")
    if output.exists():
        raise ValueError("run output must be a new directory; existing evidence is never overwritten")


@contextmanager
def new_run_output(root: Path, output: Path):
    validate_destination(root, output)
    with directory_handle(output.parent, create=True) as parent_fd:
        if parent_fd is None:
            output.mkdir(mode=0o700)
        else:
            os.mkdir(output.name, mode=0o700, dir_fd=parent_fd)
    with directory_handle(output) as output_fd:
        def publish(name: str, raw: bytes):
            if name not in {"run.json", "evidence-packet.json", "syntax.log", "cognition.log", "full.log", "local_deploy.log", "torch_probe.log"}:
                raise ValueError("unsupported run artifact")
            checked_path(output, directory=True)
            if output_fd is None:
                with (output / name).open("xb") as handle:
                    handle.write(raw)
            else:
                descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=output_fd)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(raw)
        yield publish


def probe_python(python: Path, root: Path, env: dict) -> dict:
    with tempfile.TemporaryFile() as spool:
        result = subprocess.run([str(python), "-I", "-B", "-c", PROBE], cwd=root,
                                env=env, stdout=spool, stderr=subprocess.STDOUT,
                                timeout=30, check=False, shell=False)
        spool.seek(0)
        raw = spool.read(32769)
    if result.returncode != 0 or len(raw) > 32768:
        raise ValueError("selected Python environment probe failed")
    probe = json_object(raw)
    validate_environment(probe.get("environment"))
    if (probe.get("virtualenv_reported") is not True
            or probe.get("executable") != str(python)
            or not isinstance(probe.get("prefix"), str) or not 1 <= len(probe["prefix"]) <= 4096):
        raise ValueError("selected Python must report the requested executable and a virtualenv")
    if "pytest" not in probe["environment"]["packages"]:
        raise ValueError("selected virtualenv lacks pytest; no dependencies were installed")
    return probe


def collector_digest(root: Path) -> str:
    paths = (root / "tools/termux_evidence_battery.py", root / "src/klone/evidence_run_context.py")
    return digest({p.relative_to(root).as_posix(): hashlib.sha256(read_bounded(p, 1024 * 1024)).hexdigest() for p in paths})


def stage_commands(root: Path, python: Path) -> dict:
    checked_path(root / "scripts/klone-local-torch-demo.py")
    prefix = [str(python), "-B"]
    return {
        "syntax": [*prefix, "-m", "klone.evidence_run_context", "syntax", "--source", "src/klone"],
        "cognition": [*prefix, "-m", "unittest", "discover", "-s", "tests", "-p", "test_cognition*.py", "-v"],
        "full": [*prefix, "-m", "pytest", "-p", "no:cacheprovider", "-q"],
        "local_deploy": [*prefix, "-m", "pytest", "-p", "no:cacheprovider", "-q", "tests/test_local_deploy.py"],
        "torch_probe": [*prefix, "scripts/klone-local-torch-demo.py"]
                       if (root / "scripts/klone-local-torch-demo.py").is_file() else None,
    }


def run_stage(command: list[str], root: Path, env: dict, timeout: int) -> tuple[dict, bytes]:
    timed_out = False
    with tempfile.TemporaryFile() as spool:
        try:
            completed = subprocess.run(command, cwd=root, env=env, stdout=spool,
                                       stderr=subprocess.STDOUT, timeout=timeout,
                                       check=False, shell=False)
            code = completed.returncode
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
        spool.seek(0)
        raw = spool.read(MAX_LOG + 1)
    complete = not timed_out and len(raw) <= MAX_LOG
    if len(raw) > MAX_LOG:
        note = b"\nKLONE collector: output limit exceeded; capture is incomplete.\n"
        raw = raw[:MAX_LOG - len(note)] + note
    if timed_out:
        raw = b"KLONE collector: timeout; capture is incomplete.\n" + raw[:MAX_LOG - 64]
    return {"exit_code": code, "status": "passed" if code == 0 else "failed",
            "capture_complete": complete, "timed_out": timed_out}, raw


def run_battery(root: Path, output: Path, timeout: int = 240, *, python: Path | None = None) -> dict:
    root = checked_path(root, directory=True)
    output = checked_path(output)
    validate_destination(root, output)
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be 1..3600")
    python = Path(os.path.abspath(python or root / ".venv/bin/python"))
    if not python.is_file():
        raise FileNotFoundError(str(python))
    overrides = {"PYTHONPATH": str(root / "src"), "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    env = {**os.environ, **overrides}
    if any(env.get(k) for k in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS")):
        raise ValueError("clear PYTEST_ADDOPTS and PYTEST_PLUGINS before collecting exact commands")
    before = checkout(root)
    probe = probe_python(python, root, env)
    suite_before, collector_before = suite_snapshot(root), collector_digest(root)
    commands = stage_commands(root, python)
    execution = {"context_version": 1, "cwd": str(root), "python_executable": str(python),
                 "python_prefix": probe["prefix"], "virtualenv_reported": True,
                 "commands": commands, "environment_overrides": overrides, "timeout_seconds": timeout,
                 "test_suite_before": suite_before, "collector_sha256": collector_before}
    execution["comparison_id"] = context_id(probe["environment"], execution)
    # Bound metadata before reserving the new evidence directory or executing tests.
    if len(canonical({"environment": probe["environment"], "execution": execution})) > 48000:
        raise ValueError("execution metadata limit")
    started = datetime.now(timezone.utc).isoformat()
    stages, files = {}, {}
    with new_run_output(root, output) as publish:
        for name, command in commands.items():
            if command is None:
                stage = {"exit_code": None, "status": "not_present", "capture_complete": True, "timed_out": False}
                raw = b"Optional torch demo not present in this checkout"
            else:
                stage, raw = run_stage(command, root, env, timeout)
                if name == "torch_probe" and stage["exit_code"] == 0:
                    try:
                        if json_object(raw).get("status") == "unavailable":
                            stage["status"] = "unavailable"
                    except (ValueError, UnicodeError, RecursionError):
                        pass
            stages[name] = stage
            publish(name + ".log", raw)
            files[name + ".log"] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        after = checkout(root)
        after_probe = probe_python(python, root, env)
        execution.update(test_suite_after=suite_snapshot(root), collector_after_sha256=collector_digest(root),
                         environment_after_sha256=digest(after_probe["environment"]))
        execution["context_consistent"] = (execution["test_suite_before"] == execution["test_suite_after"]
                                            and collector_before == execution["collector_after_sha256"]
                                            and probe["environment"] == after_probe["environment"])
        required_ok = all(stages[n]["status"] == "passed" for n in commands if n != "torch_probe")
        consistent = before["commit"] == after["commit"] and not before["dirty"] and not after["dirty"]
        complete = all(stage["capture_complete"] for stage in stages.values())
        report = {"schema_version": 2, "started_at": started,
                  "completed_at": datetime.now(timezone.utc).isoformat(),
                  "before": before, "after": after, "stages": stages,
                  "environment": probe["environment"], "execution": execution,
                  "required_tests_passed": required_ok, "checkout_consistent": consistent,
                  "collection_complete": complete,
                  "overall": "passed" if required_ok and consistent and complete and execution["context_consistent"] else "failed",
                  "device_identity_verified": False, "deployment_approval": False}
        validate_run(report)
        raw = json.dumps(report, indent=2, sort_keys=True).encode()
        if len(raw) > 65536:
            raise ValueError("manifest size limit")
        packet = assemble_packet(report, hashlib.sha256(raw).hexdigest(), files)
        publish("run.json", raw)
        publish("evidence-packet.json", json.dumps(packet, indent=2, sort_keys=True).encode())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "klone-next")
    parser.add_argument("--output", "--output-dir", dest="output", type=Path, required=True)
    parser.add_argument("--python", type=Path, help="Existing virtualenv interpreter, including outside the worktree")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args(argv)
    if args.timeout < 1 or args.timeout > 3600:
        parser.error("timeout must be 1..3600")
    try:
        kwargs = {"python": args.python} if args.python is not None else {}
        report = run_battery(args.root, args.output, args.timeout, **kwargs)
    except (ValueError, OSError, subprocess.SubprocessError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    return 0 if report["overall"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
