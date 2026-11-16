#!/usr/bin/env bash
# KLONE Atlas E9.1: safe Termux local tests and deduplicated source dossiers.
# No automated journal writes, no mutation of Memory Core or port 8000.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
VAR="$HOME/klone-var"
URL="http://127.0.0.1:8000/api/health"
cd "$ROOT"
test -x "$PY" || { echo "KLONE Python .venv puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_hypotheses.py" || { echo "E7-koodi puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_discovery.py" || { echo "E8-koodi puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_source_dossiers.py" || { echo "E9.1-koodi puuttuu"; exit 1; }
mkdir -p "$VAR" "$HOME/storage/downloads"

echo "=== E7/E8/E9.1 tutkimus-, turvallisuus- ja tietokantatestit ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p "test_limbo_hypotheses.py" || exit 1

echo "=== Testaa vanhojen E1–E6 rajojen säilyminen ja päivitä 8031 ==="
bash scripts/klone-atlas-e3-phone.sh || exit 1

echo "=== Varmista todellisen pää-KLONEn tietokanta ==="
TARGET="$("$PY" - <<'PY'
import json
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
opener=build_opener(ProxyHandler({}))
with opener.open("http://127.0.0.1:8000/api/health",timeout=5) as result:
    health=json.load(result)
if health.get("status")!="ok" or health.get("app")!="Klone":
    raise SystemExit("Pääpalvelin 8000 ei ole terve")
path=health.get("database_path")
if not isinstance(path,str) or not Path(path).is_file():
    raise SystemExit("Päämuistin polku ei kelpaa")
print(path)
PY
)" || exit 1
echo "Päämuistin polku: $TARGET"

echo "=== Luo E8:n ensimmäinen täysin luku-tilainen löytötutka ==="
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT="$VAR/atlas-e8-discovery-$STAMP.json"
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_discovery \
  --klone-db "$TARGET" --question "genetiikka" --limit 48 \
  --output "$REPORT" || exit 1
cp "$REPORT" "$HOME/storage/downloads/KLONE-E8-loytotutka.json"

echo "=== E9: luo todellisten lähdeparien tutkimuskortit, VAIN LUKU ==="
DOSSIERS="$VAR/atlas-e9-dossiers-$STAMP.json"
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_source_dossiers \
  --klone-db "$TARGET" --question "genetiikka" --all \
  --output "$DOSSIERS" || exit 1
cp "$DOSSIERS" "$HOME/storage/downloads/KLONE-E9-lahdeparit.json"

echo "=== E7-hypoteesin esikatselu ilman kirjoittamista ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_hypotheses \
  --journal-db "$VAR/atlas-hypotheses.sqlite3" \
  --klone-db "$TARGET" \
  --propose --domain genetics \
  --title "Genetiikan tutkimusnäytön riippumaton toistettavuus" \
  --question "Mitä riippumattomia kohortteja ja mittareita menetelmien vertailuun tarvitaan?" \
  --falsifier "Etukäteen määritelty riippumaton toistokoe ei vahvista samaa tulosta." \
  --output "$VAR/atlas-e7-preview-$STAMP.json" || exit 1

echo "=== Päivitä vain päämuistin VAIN LUKU -lukija 8041 E9.1-versioon ==="
bash scripts/klone-main-research-e8-upgrade.sh || exit 1

echo "=== Varmista E8/E9.1 rajapinnat ==="
curl -fsS --max-time 6 \
  "http://127.0.0.1:8031/api/limbo-atlas/discovery?q=genetiikka&limit=12" \
  > /dev/null || exit 1
curl -fsS --max-time 6 \
  "http://127.0.0.1:8041/api/limbo-atlas/discovery?q=genetiikka&limit=12" \
  > /dev/null || exit 1
curl -fsS --max-time 8 \
  "http://127.0.0.1:8041/api/limbo-atlas/dossiers?q=genetiikka" \
  > /dev/null || exit 1

echo "=== KLONE E7/E8/E9.1 VALMIS ==="
echo "Päämuistia tai tutkimusarkistoa ei muutettu."
echo "E8-raportti: $REPORT"
echo "E9-lähdekortit: $DOSSIERS"
echo "E7:n kirjoittamaton esikatselu: $VAR/atlas-e7-preview-$STAMP.json"
echo "Atlas: http://127.0.0.1:8031/limbo-atlas"
echo "Päämuisti: http://127.0.0.1:8041/research"
