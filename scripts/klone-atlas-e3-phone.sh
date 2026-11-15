#!/usr/bin/env bash
# KLONE Atlas E3 Termux helper: tests & restarts ONLY the service on 127.0.0.1:8031.
# Does not fetch sources automatically, modify private Memory Core, or touch ports 8000/8001.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
VAR="$HOME/klone-var"
PORT=8031
URL="http://127.0.0.1:8031"

cd "$ROOT"
test -x "$PY" || { echo "VIRHE: KLONE Python puuttuu: $PY" >&2; exit 1; }
test -f "$ROOT/src/klone/limbo_memory.py" || {
  echo "VIRHE: E3-koodi puuttuu. Päivitä työpuu GitHubista ensin." >&2
  exit 1
}

echo "=== KLONE ATLAS E3 ==="
git rev-parse --short HEAD
echo "=== Testaa E1, E2 ja E3 ==="
for filename in test_limbo_external.py test_limbo_atlas.py test_limbo_memory.py; do
  PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 \
    "$PY" -m unittest discover -s "$ROOT/tests" -p "$filename" || exit 1
done

mkdir -p "$VAR"

echo "=== Pysäytetään vain tämän työpuun 8031-palvelin ==="
KLONE_ROOT="$ROOT" "$PY" - <<'PY'
import os
from pathlib import Path
import signal
import socket
import sys
import time

root = os.path.realpath(os.environ["KLONE_ROOT"])
own = []
# Termux ps -o can reject desktop Linux formatters, so use /proc.
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        args = [x.decode("utf-8", "replace") for x in
                (proc / "cmdline").read_bytes().split(b"\0") if x]
        if not all(x in args for x in ("uvicorn", "klone.main:app", "--port", "--host")):
            continue
        if (args[args.index("--port") + 1] != "8031" or
                args[args.index("--host") + 1] != "127.0.0.1"):
            continue
        cwd = os.path.realpath(os.readlink(proc / "cwd"))
        if cwd != root:
            print("Vieraan työpuun 8031-prosessi jätetään rauhaan:", proc.name)
            continue
        own.append(int(proc.name))
    except (OSError, ValueError, IndexError):
        continue

for pid in own:
    print("Suljetaan vanha KLONE Atlas PID", pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

for _ in range(30):
    with socket.socket() as sock:
        sock.settimeout(0.3)
        busy = sock.connect_ex(("127.0.0.1", 8031)) == 0
    if not busy:
        print("Portti 8031 vapautui.")
        sys.exit(0)
    time.sleep(0.4)
raise SystemExit("Portti 8031 on edelleen varattu; vierasta palvelua ei pysäytetä.")
PY

echo "=== Käynnistetään Atlas E3 ==="
(
  cd "$ROOT" || exit 1
  KLONE_DB_PATH="$VAR/arxiv-e1.db" \
  KLONE_DATA_DIR="$VAR" \
  PYTHONPATH="$ROOT/src" \
  nohup "$PY" -m uvicorn klone.main:app \
    --host 127.0.0.1 --port "$PORT" \
    > "$VAR/atlas-e3-server.log" 2>&1 < /dev/null &
)

echo "=== Varmistetaan HTTP ==="
ready=0
for _ in $(seq 1 20); do
  if curl --silent --fail --max-time 2 "$URL/api/limbo-atlas/catalog" >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "VIRHE: Atlas E3 ei vastaa. Loki:" >&2
  tail -n 35 "$VAR/atlas-e3-server.log" >&2 || true
  exit 1
fi

for page in /api/health /api/limbo-external/agents /api/limbo-atlas/catalog /limbo-atlas; do
  curl --silent --show-error --fail --max-time 4 \
    -o /dev/null -w "$page : HTTP %{http_code}\n" "$URL$page" || exit 1
done

echo "=== VALMIS ==="
echo "$URL/limbo-atlas"
if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "$URL/limbo-atlas" || true
fi
