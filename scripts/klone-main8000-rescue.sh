#!/usr/bin/env bash
# Reanimate only the user's original localhost:8000 KLONE safely.
# Never change the original repo branch, never create a fresh Memory Core.
set -euo pipefail
ROOT="$HOME/klone"
DB="$ROOT/data/klone_mission_control.db"
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then PY="$HOME/klone-next/.venv/bin/python"; fi
VAR="$HOME/klone-var"
URL="http://127.0.0.1:8000"

echo "=== KLONE-8000 PÄÄPALVELIMEN TARKISTUS ==="
if curl -fsS --max-time 3 "$URL/api/health" >/dev/null 2>&1; then
  echo "Portti 8000 vastaa jo: ei käynnistetä toista."
  curl -fsS --max-time 3 "$URL/api/health"
  exit 0
fi

test -x "$PY" || { echo "VIRHE: Python-virtuaaliympäristö puuttuu." >&2; exit 1; }
test -f "$ROOT/src/klone/main.py" || {
  echo "VIRHE: alkuperäinen KLONE-lähdekoodi puuttuu $ROOT/src/klone/main.py" >&2
  exit 1
}
test -f "$DB" || {
  echo "VIRHE: alkuperäinen tietokanta puuttuu $DB" >&2
  echo "Uutta tyhjää tietokantaa ei luoda. Tarkista oikea pääpalvelimen polku." >&2
  exit 1
}
"$PY" - <<'PY'
import socket
with socket.socket() as sock:
    sock.settimeout(2)
    if sock.connect_ex(("127.0.0.1",8000)) == 0:
        raise SystemExit("VIRHE: portti 8000 on varattu; ei käynnistetä rinnalle.")
PY

mkdir -p "$VAR/backups"
chmod 700 "$VAR/backups"
BACKUP="$VAR/backups/klone-main-before-restart-$(date +%Y%m%d-%H%M%S).sqlite3"
echo "=== VANHAN PÄÄMUISTIN EHEYSTARKISTUS JA VARMUUSKOPIO ==="
echo "Lähdekoodi: $ROOT"
echo "Päämuistin tietokanta: $DB"
"$PY" - "$DB" "$BACKUP" <<'PY'
import os
import sqlite3
import stat
import sys
from pathlib import Path
source=Path(sys.argv[1]).expanduser()
backup=Path(sys.argv[2]).expanduser()
if source.is_symlink():
    raise SystemExit("VIRHE: tietokannan symbolinen linkki estetty")
info=source.stat()
if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
    raise SystemExit("VIRHE: päämuistin tietokanta ei ole tavallinen tiedosto")
if source.resolve()==backup.resolve() or backup.exists():
    raise SystemExit("VIRHE: varmuuskopio on jo olemassa")
with sqlite3.connect(source.resolve().as_uri()+"?mode=ro",uri=True,timeout=30) as conn:
    tables={r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"memory_events","audit_events"}<=tables:
        raise SystemExit("VIRHE: tämä ei ole olemassa oleva KLONE Memory Core")
    if conn.execute("PRAGMA quick_check").fetchone()[0]!="ok":
        raise SystemExit("VIRHE: alkuperäisen muistin eheystarkistus ei onnistunut")
    with sqlite3.connect(backup,timeout=30) as destination:
        conn.backup(destination,pages=128,sleep=.1)
os.chmod(backup,0o600)
with sqlite3.connect(backup) as conn:
    if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
        backup.unlink(missing_ok=True)
        raise SystemExit("VIRHE: varmuuskopion eheystarkistus ei onnistunut")
print("Varmuuskopio eheä:",backup)
PY

echo "=== KÄYNNISTETÄÄN VAIN ALKUPERÄINEN PORTTI 8000 ==="
(
 cd "$ROOT"
 KLONE_DB_PATH="$DB" KLONE_DATA_DIR="$ROOT/data" PYTHONPATH="$ROOT/src" \
 nohup "$PY" -m uvicorn klone.main:app --host 127.0.0.1 --port 8000 \
   > "$VAR/main8000-rescue.log" 2>&1 < /dev/null &
)
ready=0
for _ in $(seq 1 20); do
 if curl -fsS --max-time 2 "$URL/api/health" >/dev/null 2>&1; then
   ready=1;break
 fi
 sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "VIRHE: 8000 ei vastaa. Loki:"
  tail -n 35 "$VAR/main8000-rescue.log" || true
  exit 1
fi

"$PY" - "$DB" <<'PY'
import json,sys
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
opener=build_opener(ProxyHandler({}))
with opener.open("http://127.0.0.1:8000/api/health",timeout=5) as r:
    health=json.load(r)
print("status:",health.get("status"))
print("app:",health.get("app"))
print("database_path:",health.get("database_path"))
if (health.get("status")!="ok" or health.get("app")!="Klone"
    or Path(str(health.get("database_path"))).resolve()!=Path(sys.argv[1]).resolve()):
    raise SystemExit("VIRHE: pääpalvelin käyttää odottamatonta tietokantaa.")
PY
echo "VALMIS: vanha pää-KLONE vastaa portissa 8000."
echo "Huomio: portteja 8001, 8031 tai 8041 ei muutettu."
