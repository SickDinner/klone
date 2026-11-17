#!/usr/bin/env bash
# KLONE E11.4 private quality triage, no service restarts, no main DB writes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
WORK="$HOME/klone-var/e11"
test -x "$PY" || { echo "KLONE Python puuttuu"; exit 1; }
test -f "$DB" || { echo "Päämuisti puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_evidence_quality.py" || {
  echo "E11.4-moduuli puuttuu: hae uusin GitHub-versio"; exit 1;
}
if [ "$#" -eq 0 ]; then
  PAIR="$("$PY" - <<'PY'
from pathlib import Path
root=Path.home()/"klone-var"/"e11"
selected=sorted(root.glob("e11-3-konteksti-*.json"))
for item in reversed(selected):
    suffix=item.name[len("e11-3-konteksti-"):]
    ledger=root/("e11-3-tarkistus-"+suffix)
    if ledger.is_file():
        print(item)
        print(ledger)
        break
else:
    raise SystemExit("E11.3:n vastaavia manifesti- ja tarkistusraportteja ei löytynyt")
PY
)" || exit 1
  SELECTED="$(printf '%s\n' "$PAIR" | sed -n '1p')"
  LEDGER="$(printf '%s\n' "$PAIR" | sed -n '2p')"
elif [ "$#" -eq 2 ]; then
  SELECTED="$1"
  LEDGER="$2"
else
  echo "Käyttö: bash scripts/klone-e11-4-phone.sh [E11.3_CONTEXT.json E11.3_LEDGER.json]"
  exit 2
fi
test -f "$SELECTED" || { echo "Hyväksytty manifesti puuttuu: $SELECTED"; exit 1; }
test -f "$LEDGER" || { echo "Tarkistettu evidenssiraportti puuttuu: $LEDGER"; exit 1; }
ORIGINAL="$WORK/e11-taytetty.json"
test -f "$ORIGINAL" || { echo "Alkuperäinen E11-manifesti puuttuu: $ORIGINAL"; exit 1; }
PROPOSALS="$("$PY" - "$SELECTED" <<'PY'
import json,sys
from pathlib import Path
selected=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
digest=selected["e11_context_selection"]["e11_2_report_sha256"]
directory=Path.home()/"klone-var"/"e11"
for file in sorted(directory.glob("e11-2-ehdokkaat-*.json")):
    candidate=json.loads(file.read_text(encoding="utf-8"))
    if candidate.get("report_sha256")==digest:
        print(file)
        break
else:
    raise SystemExit("E11.2:n täsmäävää alkuperäistä ehdotusraporttia ei löytynyt")
PY
)" || exit 1
test -f "$PROPOSALS" || { echo "E11.2-ehdotusraportti puuttuu"; exit 1; }
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-4-laatuauditointi-$STAMP.json"
cd "$ROOT"
echo "=== E11.4: paikalliset testit ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p test_limbo_hypotheses.py || exit 1
echo "=== E11.4: laadunvalvonta – EI tieteellisiä johtopäätöksiä ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_evidence_quality \
  --klone-db "$DB" --original "$ORIGINAL" --proposals "$PROPOSALS" \
  --selected "$SELECTED" --ledger "$LEDGER" --output "$OUTPUT"
"$PY" - "$OUTPUT" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("Lähteet:",*r["source_event_ids"])
print("Kontekstimerkintöjä:",r["context_quote_count"])
print("Triage:")
for k,v in sorted(r["counts_by_kind"].items()):
    print(" ",k,":",v)
print("Tieteellisesti varmennettuja:",r["scientifically_verified_quote_count"])
print("Neuvostoarviointeja:",r["independent_council_reviews"])
print("Muistikirjoituksia:",r["memory_write"])
PY
echo "Valmis, raportti: $OUTPUT"
