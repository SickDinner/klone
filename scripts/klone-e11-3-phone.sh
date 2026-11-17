#!/usr/bin/env bash
# E11.3: explicit owner decision to classify E11.2 local quotes as CONTEXT ONLY.
# No original paper verification, no E7 journal writes or Council72 vote.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
E11="$HOME/klone-var/e11"
MANIFEST="$E11/e11-taytetty.json"
cd "$ROOT"
test -x "$PY" || { echo "KLONE Python puuttuu"; exit 1; }
test -f "$MANIFEST" || { echo "Täytetty E11-manifesti puuttuu"; exit 1; }
if [ "$#" -eq 1 ]; then
  PROPOSALS="$1"
elif [ "$#" -eq 0 ]; then
  PROPOSALS="$("$PY" - <<'PY'
from pathlib import Path
folder=Path.home()/"klone-var"/"e11"
items=sorted(folder.glob("e11-2-ehdokkaat-*.json"))
if not items:
    raise SystemExit("E11.2-ehdotusraporttia ei löytynyt, aja ensin klone-e11-2-phone.sh")
print(items[-1])
PY
)" || exit 1
else
  echo "Käyttö: bash scripts/klone-e11-3-phone.sh [E11.2_REPORT.json]"
  exit 1
fi
test -f "$PROPOSALS" || { echo "E11.2-ehdotusraportti puuttuu: $PROPOSALS"; exit 1; }
echo "=== E11.3: tarkista ehdotukset, ei automaattista hyväksyntää ==="
"$PY" - "$PROPOSALS" <<'PY'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text())
if data.get("kind")!="klone-e11-2-evidence-review-candidates":
    raise SystemExit("Väärä ehdotusraportti")
print("Pari:",data.get("source_event_ids"))
print("Ehdotettuja asiayhteyslainauksia:",data.get("candidate_count"))
for role in ("A","B"):
    info=data["source_info"][role]
    print("Lähde",role,":",info["content_origin"])
print("HUOM: paikalliset selostukset EIVÄT ole varmennettuja alkuperäisjulkaisuja.")
print("Tämä lisää vain kontekstimerkinnät. 0 tutkimuspäätöstä, 0 neuvostoääntä.")
PY
echo "Anna nimenomainen hyväksyntä E11.2:n kaikille asiayhteyskatkelmille."
echo "Jos et halua hyväksyä kaikkia, keskeytä Ctrl+C ja valitse myöhemmin ID:t erikseen."
read -r -p "Kirjoita HYVAKSY KONTEKSTI jatkaaksesi: " CONFIRMATION
if [ "$CONFIRMATION" != "HYVAKSY KONTEKSTI" ]; then
  echo "Ei hyväksyntää; ei luotu uusia tiedostoja."
  exit 2
fi
STAMP="$(date +%Y%m%d-%H%M%S)"
APPROVED="$E11/e11-3-konteksti-$STAMP.json"
REVIEWED="$E11/e11-3-tarkistus-$STAMP.json"
echo "=== Vahvistettu kontekstivalinta; E11.3 revalidointi ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_evidence_accept \
  --klone-db "$DB" --manifest "$MANIFEST" \
  --proposals "$PROPOSALS" --all-context \
  --owner-confirms-candidate-selection --output "$APPROVED"
echo "=== Ankkuroitujen lainauksien E11 offline-tarkistus ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_evidence_review \
  --klone-db "$DB" --review "$APPROVED" --output "$REVIEWED"
"$PY" - "$REVIEWED" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text())
assert r["annotation_count"]>=1
assert not any(r["authority"].values())
assert r["council_state"]["recorded_votes"]==0
print("Asiayhteyteen ankkuroidut lainaukset:",r["annotation_count"])
print("Tieteellisesti vahvistettu:",r["authority"]["scientific_truth_verified"])
print("Päämuistikirjoitukset:",r["authority"]["memory_write"])
PY
echo "=== Vahvistettu manifesti: $APPROVED ==="
echo "=== Offline-evidenssiraportti: $REVIEWED ==="
