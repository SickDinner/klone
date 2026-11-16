#!/usr/bin/env bash
# Safe owner-gated KLONE Atlas E5 Memory Core import in Android Termux.
# Only localhost status is queried; no remote posting, no hidden write.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
SOURCE="$HOME/klone-var/atlas-memory.sqlite3"
mkdir -p "$HOME/klone-var"
cd "$ROOT"

test -x "$PY" || { echo "Python-virtuaaliympäristö puuttuu." >&2; exit 1; }
test -f "$SOURCE" || { echo "E3-tutkimusarkistoa ei löydy: $SOURCE" >&2; exit 1; }

echo "=== 1. Tarkista käynnissä olevan KLONEn 8031 todellinen Memory Core -kanta ==="
TARGET="$("$PY" - <<'PY'
import json
from pathlib import Path
from urllib.request import urlopen
try:
    with urlopen("http://127.0.0.1:8031/api/health",timeout=4) as answer:
        if answer.status != 200:
            raise ValueError("Health check not HTTP 200")
        data=json.load(answer)
    path=data.get("database_path")
    if data.get("status")!="ok" or data.get("app")!="Klone":
        raise ValueError("Not the intended running KLONE service")
    if not isinstance(path,str) or not path or not Path(path).is_file():
        raise ValueError("No valid KLONE Memory Core database_path in health")
    print(path)
except Exception as exc:
    raise SystemExit("KLONE 8031 health verification failed: "+str(exc))
PY
)" || exit 1

echo "Käynnissä olevan KLONEn kanta: $TARGET"
echo "E3-julkisen tutkimusarkiston kanta: $SOURCE"
echo "=== 2. Esikatsele muutokset, älä kirjoita vielä ==="
PREVIEW="$HOME/klone-var/atlas-e5-preview-$(date +%Y%m%d-%H%M%S).json"

PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_memory_bridge \
  --atlas-db "$SOURCE" \
  --klone-db "$TARGET" \
  --output "$PREVIEW" || exit 1

echo "=== 3. Pyydä nimenomainen omistajan hyväksyntä ==="
"$PY" - "$PREVIEW" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding="utf-8"))
print("Uusia KLONE-muistimerkintöjä:",p["new_events"])
print("Ennestään muistissa:",p["already_present"])
print("Huone:",p["room_id"],"luokitus:",p["classification_level"])
print("Tallennuksen tila:",p["mode"])
print("Väitteet vahvistettu:",False)
PY

printf 'Kirjoita TUO hyväksyäksesi vain julkisten lähdetietojen tuonnin KLONE-älymuistiin: '
read -r CONFIRM
if [ "$CONFIRM" != "TUO" ]; then
  echo "Tuonti peruttu: muistia ei muutettu."
  exit 0
fi

echo "=== 4. Tuodaan julkiset tutkimusviitteet todelliseen Memory Coreen ==="
OUT="$HOME/klone-var/atlas-e5-import-$(date +%Y%m%d-%H%M%S).json"
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_memory_bridge \
  --atlas-db "$SOURCE" \
  --klone-db "$TARGET" \
  --commit \
  --output "$OUT" || exit 1

echo "=== 5. Tarkista tutkimusmuistin haku ==="
curl --silent --show-error --fail \
  "http://127.0.0.1:8031/api/memory/events?room_id=research-room&limit=1" \
  >/dev/null
curl --silent --show-error --fail \
  "http://127.0.0.1:8031/api/limbo-atlas/memory/recall?q=genetics&limit=2" \
  >/dev/null

echo "KLONE Atlas E5 -julkisen tutkimusmuistin tuonti valmistui."
echo "Audit ja alkuperäislähteiden viitteet ovat Memory Coressa."
echo "Koko raportti: $OUT"
if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "http://127.0.0.1:8031/limbo-atlas" || true
fi
