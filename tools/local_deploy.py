"""Cross-platform local-only KLONE launcher (Windows and Termux).

Run from repository root: python tools/local_deploy.py doctor|install|start
No LAN binding, secret upload, remote deployment, or background daemon.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.error
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
HOST = "127.0.0.1"
PORT = 8000


def python_path() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def doctor() -> int:
    errors = []
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ required")
    if not (ROOT / "pyproject.toml").is_file():
        errors.append("Run from a complete KLONE checkout")
    if not (ROOT / "src" / "klone" / "main.py").is_file():
        errors.append("Missing KLONE app entrypoint")
    print(f"KLONE root: {ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    print(f"Local URL: http://{HOST}:{PORT}/")
    print(f"Virtual environment: {'ready' if python_path().is_file() else 'missing'}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


def install() -> int:
    if doctor():
        return 1
    if not python_path().is_file():
        venv.EnvBuilder(with_pip=True).create(VENV)
    return subprocess.call([
        str(python_path()), "-m", "pip", "install", "-e", str(ROOT),
    ], cwd=ROOT)


def start(port: int) -> int:
    if doctor():
        return 1
    if not python_path().is_file():
        print("Run install first", file=sys.stderr)
        return 2
    if not 1024 <= port <= 65535:
        print("Port must be 1024..65535", file=sys.stderr)
        return 2
    with socket.socket() as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            print(f"Port {port} is unavailable; choose --port 8001", file=sys.stderr)
            return 2
    print(f"KLONE local-only: http://{HOST}:{port}/", flush=True)
    return subprocess.call([
        str(python_path()), "-m", "uvicorn", "klone.main:app",
        "--host", HOST, "--port", str(port),
    ], cwd=ROOT)


def healthcheck(port: int = PORT) -> int:
    if not 1024 <= port <= 65535:
        print("Invalid port", file=sys.stderr)
        return 2
    url = f"http://{HOST}:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                raise ValueError("unexpected_http_status")
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError("oversized_health_response")
        data = json.loads(body)
        if (not isinstance(data, dict) or data.get("status") != "ok"
                or not isinstance(data.get("app_version"), str)
                or not data["app_version"]):
            raise ValueError("not_klone_health")
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"KLONE healthcheck failed: {error}", file=sys.stderr)
        return 1
    print(f"KLONE healthy at {url}, version={data['app_version']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "install", "start", "healthcheck"))
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "install":
        return install()
    if args.command == "healthcheck":
        return healthcheck(args.port)
    return start(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
