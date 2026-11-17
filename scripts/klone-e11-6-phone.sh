#!/usr/bin/env bash
# KLONE E11.6: explicit and limited public arXiv Atom metadata intake.
# Default is OFFLINE preview. --fetch also requires typed owner confirmation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
WORK="$HOME/klone-var/e11"
ORIGINAL="$WORK/e11-taytetty.json"
if [ "$#" -gt 1 ]; then
  echo "Käyttö: bash scripts/klone-e11-6-phone.sh [--fetch]"
  exit 2
fi
if [ "$#" -eq 1 ] && [ "$1" != "--fetch" ]; then
  echo "Käyttö: bash scripts/klone-e11-6-phone.sh [--fetch]"
  exit 2
fi
test -x "$PY" || { echo "KLONE Python puuttuu"; exit 1; }
test -f "$DB" || { echo "KLONE-päämuisti puuttuu"; exit 1; }
test -f "$ORIGINAL" || { echo "E11-alkuperäinen lähdemanifesti puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_arxiv_primary.py" || {
  echo "E11.6-moduuli puuttuu, päivitä GitHub-haara"; exit 1;
}
PAIR="$("$PY" - "$ORIGINAL" <<'PY'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
a=data["sources"]["A"]["event_id"]
b=data["sources"]["B"]["event_id"]
if type(a) is not int or type(b) is not int or a<=0 or b<=0 or a==b:
    raise SystemExit("E11: virheellinen lähdepari")
print(a,b)
PY
)" || exit 1
read -r FIRST SECOND <<< "$PAIR"
mkdir -p "$WORK"
cd "$ROOT"
echo "=== E11.6: testaa tutkimusregressiot (ei vielä verkkohakua) ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p test_limbo_hypotheses.py || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"
PLAN="$WORK/e11-6-arxiv-esikatselu-$STAMP.json"
echo "=== E11.6: lähde-ID ja alkuperäispolkujen tarkistus, vain luku ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_arxiv_primary \
  --klone-db "$DB" --pair "$FIRST" "$SECOND" --output "$PLAN"
echo "E11.6-esikatselu: $PLAN"
if [ "$#" -eq 0 ]; then
  echo "VERKKOA EI KÄYTETTY. ArXiv-tiivistelmien haku vaatii --fetch ja erillisen hyväksynnän."
  exit 0
fi
echo "=== Kysy erillinen lupa ==="
echo "Vain julkisen arXiv Atom -rajapinnan kaksi versionumeroon sidottua tiivistelmää."
echo "Ei PDF-tiedostoja, ei muita verkkohakuja, ei agenttien suorittamia arviointeja."
echo "URL muodostetaan kanonisista Memory Core -arXiv-tunnisteista ilman käyttäjän URL-parametreja."
read -r -p "Kirjoita HYVAKSY ARXIV, jotta voin hakea julkiset metatiedot: " APPROVAL
if [ "$APPROVAL" != "HYVAKSY ARXIV" ]; then
  echo "Ei lupaa. Julkaisuja ei haettu eikä mitään muuta muutettu."
  exit 2
fi
RECEIPT="$WORK/e11-6-arxiv-vastaukset-$STAMP.json"
echo "=== E11.6: yksi sallittu HTTPS GET, rajattu arXiv Atom ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_arxiv_primary \
  --klone-db "$DB" --pair "$FIRST" "$SECOND" \
  --fetch --owner-authorizes-public-read --output "$RECEIPT"
"$PY" - "$RECEIPT" <<'PY'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("Vastaanotettu arXiv-julkaisumetatietoja:",len(data["documents"]))
print("Molemmat otsikot täsmäävät muistiviitteisiin:",data["metadata_title_pair_matches_memory"])
for doc in data["documents"]:
    print(" •",doc["arxiv_id"],"muisti-ID",doc["memory_event_id"],
          "otsikko täsmää:",doc["title_matches_memory"],
          "tiivistelmän tarkiste:",doc["abstract_sha256"][:16])
print("Koko tutkimuksen validointi:",data["scientific_truth_verified"])
print("Täysi julkaisuteksti:",data["primary_full_text_fetched"])
print("Päämuistikirjoitukset:",data["memory_write"])
PY
echo "ArXiv-metatietotositteet: $RECEIPT"
