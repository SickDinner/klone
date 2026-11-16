#!/usr/bin/env bash
# Safe read-only research canary against port 8000's real KLONE Memory Core DB.
# Does not open the database for writes; does not alter port 8000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
LOG="$HOME/klone-var/main-research-canary.log"
URL="http://127.0.0.1:8041"
cd "$ROOT"
test -x "$PY" || { echo "E6: Python-ympäristö puuttuu"; exit 1; }
mkdir -p "$HOME/klone-var"
TARGET="$("$PY" - <<'PY'
import json
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
opener=build_opener(ProxyHandler({}))
with opener.open("http://127.0.0.1:8000/api/health",timeout=5) as r:
    data=json.load(r)
if data.get("app")!="Klone" or data.get("status")!="ok":
    raise SystemExit("Pääpalvelimen health ei ole ok")
path=data.get("database_path")
if not isinstance(path,str) or not Path(path).is_file():
    raise SystemExit("Päämuistin polku puuttuu")
print(path)
PY
)" || exit 1

echo "Pää-KLONEn tietokanta: $TARGET"
echo "=== VAIN LUKU -KATSELU PORTISSA 8041 ==="
set +e
KLONE_MAIN_RESEARCH_DB="$TARGET" "$PY" - <<'PY'
import json,os,socket,sys
from urllib.request import build_opener,ProxyHandler
with socket.socket() as s:
    s.settimeout(0.5)
    busy=s.connect_ex(("127.0.0.1",8041))==0
if busy:
    opener=build_opener(ProxyHandler({}))
    try:
        with opener.open("http://127.0.0.1:8041/health",timeout=3) as response:
            state=json.load(response)
    except Exception as error:
        raise SystemExit("Portti 8041 on varattu toiselle palvelulle: "+str(error))
    if (state.get("service")!="klone-main-research-readonly"
        or state.get("read_only") is not True
        or state.get("database_path")!=os.environ["KLONE_MAIN_RESEARCH_DB"]):
        raise SystemExit("Portissa 8041 on väärä tai vanhentunut palvelin; ei käynnistetä rinnalle")
    print("Sama read-only canary on jo käynnissä.")
    sys.exit(12)
PY
result=$?
set -e
if [ "$result" -eq 12 ]; then exit 0; fi
if [ "$result" -ne 0 ]; then exit "$result"; fi

(
  cd "$ROOT"
  KLONE_MAIN_RESEARCH_DB="$TARGET" PYTHONPATH="$ROOT/src" \
  nohup "$PY" -m uvicorn klone.limbo_main_research_canary:app \
    --host 127.0.0.1 --port 8041 \
    > "$LOG" 2>&1 < /dev/null &
)

ready=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 2 "$URL/health" > /dev/null; then
    ready=1; break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "E6:n vain luku -katselu ei käynnistynyt. Loki:"
  tail -n 25 "$LOG" || true
  exit 1
fi
"$PY" - "$TARGET" <<'PY'
import json,sys
from urllib.request import build_opener,ProxyHandler
with build_opener(ProxyHandler({})).open(
        "http://127.0.0.1:8041/health",timeout=3) as r:
    data=json.load(r)
if data.get("database_path")!=sys.argv[1] or data.get("read_only") is not True:
    raise SystemExit("Read-only canary ei osoita oikeaan päämuistiin")
print("Päämuisti on liitetty E6:n VAIN LUKU -tutkimusnäkymään.")
PY
echo "Päämuistin E6-tutkimustyöpöytä: $URL/research"
echo "E6-päämuistihaku: $URL/api/limbo-atlas/intelligence?q=genetiikka"
echo "Vain luku. Ei muutoksia päämuistiin eikä pääpalvelimeen 8000."
if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "$URL/research" || true
fi
