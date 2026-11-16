#!/usr/bin/env bash
# Explicit main KLONE (port 8000) Memory Core integration.
# Never restart port 8000, touch another room or import without owner's approval.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
ATLAS_DB="$HOME/klone-var/atlas-memory.sqlite3"
HEALTH_URL="http://127.0.0.1:8000"
cd "$ROOT"
test -x "$PY" || { echo "Python venv puuttuu." >&2; exit 1; }
test -f "$ATLAS_DB" || { echo "Atlas E3 -muisti puuttuu." >&2; exit 1; }
mkdir -p "$HOME/klone-var"
REPORT="$HOME/klone-var/main-memory-health-$(date +%Y%m%d-%H%M%S).json"

echo "=== PÄÄPALVELIMEN 8000 TODELLINEN TIETOKANTA JA HUONEET ==="
"$PY" - "$REPORT" <<'PY'
import json,sys
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
opener=build_opener(ProxyHandler({}))
base="http://127.0.0.1:8000"
with opener.open(base+"/api/health",timeout=5) as response:
    if response.status!=200:raise SystemExit("Portin 8000 health ei vastaa")
    health=json.load(response)
if health.get("status")!="ok" or health.get("app")!="Klone":
    raise SystemExit("Portti 8000 ei ole terve KLONE")
target=health.get("database_path")
if not isinstance(target,str) or not Path(target).is_file():
    raise SystemExit("Pääpalvelimen database_path ei ole kelvollinen")
with opener.open(base+"/api/rooms",timeout=5) as response:
    rooms=json.load(response)
ready=any(isinstance(r,dict) and r.get("id")=="research-room"
          and r.get("classification")=="public"
          and "read" in r.get("permissions",[]) for r in rooms)
data={"main_db_path":target,"research_room_ready":ready}
Path(sys.argv[1]).write_text(json.dumps(data,indent=2),encoding="utf-8")
print("Pääpalvelimen tietokanta:",target)
print("Tuntee public research-room -huoneen:",ready)
PY

TARGET="$("$PY" - "$REPORT" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding="utf-8"))["main_db_path"])
PY
)"
echo "=== KIRJOITTAMATON ESIKATSELU ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_memory_bridge \
  --atlas-db "$ATLAS_DB" --klone-db "$TARGET" \
  --output "$HOME/klone-var/main-memory-preview-$(date +%Y%m%d-%H%M%S).json"

READY="$("$PY" - "$REPORT" <<'PY'
import json,sys
print("yes" if json.load(open(sys.argv[1],encoding="utf-8"))["research_room_ready"] else "no")
PY
)"
if [ "$READY" != "yes" ]; then
  echo "Pääpalvelin 8000 ei tunne vielä research-roomia."
  echo "Varmistetaan sen rinnalla käynnissä oleva eristetty, VAIN LUKU -E6-palvelu."
  "$PY" - "$TARGET" <<'PY'
import json,sys
from urllib.request import build_opener,ProxyHandler
o=build_opener(ProxyHandler({}))
try:
    with o.open("http://127.0.0.1:8041/health",timeout=4) as r:
        data=json.load(r)
except Exception as exc:
    raise SystemExit("TURVARAJA: Portti 8041 ei vastaa: "+str(exc)+
                     ". Käynnistä ensin bash scripts/klone-main-research-canary.sh")
if (data.get("service")!="klone-main-research-readonly"
    or data.get("read_only") is not True
    or data.get("database_path")!=sys.argv[1]
    or data.get("room_scope")!="research-room"):
    raise SystemExit("TURVARAJA: Väärä päämuistin E6-lukija. EI KIRJOITETA.")
print("Oikea 8000:n päämuisti on 8041:n read-only tutkimuslukijan kohteena.")
PY
fi

echo "=== TURVALLINEN SQLITE-ONLINE-VARMUUSKOPIO ==="
BACKUP_DIR="$HOME/klone-var/backups"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
BACKUP="$BACKUP_DIR/main-pre-e6-$(date +%Y%m%d-%H%M%S).sqlite3"
"$PY" - "$TARGET" "$BACKUP" <<'PY'
import os,sqlite3,sys
from pathlib import Path
source=Path(sys.argv[1]).resolve(strict=True)
backup=Path(sys.argv[2])
if backup.exists() or source==backup.resolve():raise SystemExit("Varmuuskopio jo olemassa")
with sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=30) as original:
    with sqlite3.connect(backup,timeout=30) as destination:
        original.backup(destination,pages=128,sleep=0.10)
os.chmod(backup,0o600)
with sqlite3.connect(backup) as verify:
    if verify.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
        raise SystemExit("Varmuuskopion eheystarkistus epäonnistui")
print("Eheä varmuuskopio:",backup)
PY

echo "Tämä muuttaa portin 8000 oikeaa KLONE Memory Corea."
printf 'Vahvista kirjoittamalla PAAMUISTI: '
read -r CONFIRM
if [ "$CONFIRM" != "PAAMUISTI" ]; then
  echo "Peruttu: päämuistiin ei tehty muutoksia."
  exit 0
fi

# Recheck immediately before a write. Fail closed if the target changed.
"$PY" - "$TARGET" <<'PY'
import json,sys
from urllib.request import build_opener,ProxyHandler
o=build_opener(ProxyHandler({}))
with o.open("http://127.0.0.1:8000/api/health",timeout=5) as r:h=json.load(r)
with o.open("http://127.0.0.1:8000/api/rooms",timeout=5) as r:rooms=json.load(r)
if h.get("database_path")!=sys.argv[1]:
    raise SystemExit("Pääpalvelimen tietokantapolku muuttui. Kirjoitus estetty.")
room_ready=any(x.get("id")=="research-room" and x.get("classification")=="public" for x in rooms)
if not room_ready:
    try:
        with o.open("http://127.0.0.1:8041/health",timeout=5) as r:canary=json.load(r)
    except Exception as exc:
        raise SystemExit("Päämuistin vain luku -tutkimuslukija ei vastaa: "+str(exc))
    if (canary.get("service")!="klone-main-research-readonly"
        or canary.get("database_path")!=sys.argv[1]
        or canary.get("read_only") is not True
        or canary.get("room_scope")!="research-room"):
        raise SystemExit("TURVARAJA: Päämuisti ei ole turvallisesti luettavissa. EI KIRJOITETA.")
PY
echo "=== HYVÄKSYTTY TUTKIMUSMETATIETOJEN TUONTI ==="
OUTPUT="$HOME/klone-var/main-e6-import-$(date +%Y%m%d-%H%M%S).json"
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_memory_bridge \
  --atlas-db "$ATLAS_DB" --klone-db "$TARGET" --commit --output "$OUTPUT"
if [ "$READY" = "yes" ]; then
  curl --fail --silent --show-error --max-time 5 \
    "$HEALTH_URL/api/memory/events?room_id=research-room&limit=1" >/dev/null
else
  curl --fail --silent --show-error --max-time 5 \
    "http://127.0.0.1:8041/api/limbo-atlas/memory/recall?q=genetiikka&limit=1" >/dev/null
  echo "Pääpalvelimen 8000 vanha käyttöliittymä ei vielä näytä tutkimushuonetta."
  echo "Uusi tutkimusmuisti on luettavissa portin 8041 kautta."
fi
echo "Päämuistin tuonti valmis: $OUTPUT"
echo "Varmuuskopio: $BACKUP"
