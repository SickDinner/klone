#!/usr/bin/env bash
# Upgrade only KLONE's dedicated localhost:8041 read-only research sidecar.
# Main port 8000 and Atlas 8031 are never stopped.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
cd "$ROOT"
test -x "$PY" || { echo "Python .venv puuttuu"; exit 1; }

echo "=== Tarkista alkuperäisen päämuistin todellinen polku ==="
set +e
KLONE_ROOT="$ROOT" "$PY" - <<'PY'
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time
from urllib.request import build_opener,ProxyHandler

opener=build_opener(ProxyHandler({}))
with opener.open("http://127.0.0.1:8000/api/health",timeout=5) as response:
    main=json.load(response)
if main.get("status")!="ok" or main.get("app")!="Klone":
    raise SystemExit("Portin 8000 pääpalvelin ei ole terve KLONE")
db=main.get("database_path")
if not isinstance(db,str) or not Path(db).is_file():
    raise SystemExit("Päämuistin tietokantapolku puuttuu")

with socket.socket() as sock:
    sock.settimeout(1)
    busy=sock.connect_ex(("127.0.0.1",8041))==0
if not busy:
    print("Portti 8041 vapaa. Käynnistetään uusi E8-lukija.")
    sys.exit(0)

with opener.open("http://127.0.0.1:8041/health",timeout=4) as response:
    health=json.load(response)
if (health.get("service")!="klone-main-research-readonly"
    or health.get("read_only") is not True
    or health.get("database_path")!=db
    or health.get("room_scope")!="research-room"):
    raise SystemExit("Portti 8041 on väärä palvelu tai eri tietokanta. Ei pysäytetä.")

if health.get("feature_version")=="E9":
    print("E8-päämuistilukija on jo käytössä.")
    sys.exit(12)

root=os.path.realpath(os.environ["KLONE_ROOT"])
candidates=[]
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name)==os.getpid():
        continue
    try:
        args=[x.decode("utf-8","replace") for x in
              (proc/"cmdline").read_bytes().split(b"\0") if x]
        if not all(t in args for t in ("uvicorn","klone.limbo_main_research_canary:app",
                                       "--port","--host")):
            continue
        if (args[args.index("--port")+1]!="8041"
            or args[args.index("--host")+1]!="127.0.0.1"):
            continue
        cwd=os.path.realpath(os.readlink(proc/"cwd"))
        if cwd!=root:continue
        candidates.append(int(proc.name))
    except (OSError,IndexError,ValueError):
        continue

if len(candidates)!=1:
    raise SystemExit("Portin 8041 omistajaprosessia ei tunnistettu yksiselitteisesti."
                     " Pääpalvelinta ei muutettu.")
print("Pysäytetään vain vanha 8041-lukija PID:",candidates[0])
os.kill(candidates[0],signal.SIGTERM)

for _ in range(40):
    with socket.socket() as sock:
        sock.settimeout(.3)
        busy=sock.connect_ex(("127.0.0.1",8041))==0
    if not busy:
        print("8041 vapautui, käynnistetään uusi versio.")
        sys.exit(0)
    time.sleep(.25)
raise SystemExit("8041 ei vapautunut: uutta prosessia ei käynnistetä.")
PY
result=$?
set -e
if [ "$result" -eq 12 ]; then
  termux-open-url http://127.0.0.1:8041/research || true
  exit 0
fi
if [ "$result" -ne 0 ]; then exit "$result"; fi

bash scripts/klone-main-research-canary.sh || exit 1

"$PY" - <<'PY'
import json
from urllib.request import build_opener,ProxyHandler
opener=build_opener(ProxyHandler({}))
with opener.open("http://127.0.0.1:8041/health",timeout=5) as r:
    h=json.load(r)
if h.get("read_only") is not True or h.get("feature_version")!="E9":
    raise SystemExit("E8-lukijan versiotarkistus epäonnistui")
print("Päämuistin E8-lukija on valmis:",h["feature_version"])
PY
