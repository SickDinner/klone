#!/usr/bin/env bash
# KLONE E10 Doctor: read-only status for existing original main and sidecars.
# Never start/stop services, migrate DB, read private memory or import sources.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HOME/klone-var/klone-doctor-e10-$STAMP.json"
test -x "$PY" || { echo "Venv-pyton puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_doctor.py" || { echo "E10-doctorin lähdekoodi puuttuu"; exit 1; }
test -f "$DB" || { echo "Alkuperäinen päämuisti puuttuu: $DB"; exit 1; }
mkdir -p "$HOME/klone-var"
cd "$ROOT"
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_doctor \
  --expected-main-db "$DB" --output "$OUT"
"$PY" - "$OUT" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text())
print("=== KLONE E10 DOCTOR ===")
print("Tila:",r["health"])
for k,v in r["services"].items():
    print(k,"OK" if v["ok"] else "TARKISTETTAVA",v.get("version",v.get("error")))
print("Päämuistin eheys:",r["main_database"].get("quick_check","ei tarkistettu"))
print("Julkiset tutkimusmuistot:",
      r["main_database"].get("active_public_research_events","ei tarkistettu"))
print("Mahdolliset ongelmat:",", ".join(r["problems"]) or "ei havaittu")
print("Päämuistia ei muutettu.")
PY
echo "Raportti: $OUT"
