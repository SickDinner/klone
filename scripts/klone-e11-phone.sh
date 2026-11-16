#!/usr/bin/env bash
# E11 preparation ONLY: no fetch, DB changes, service restarts or invented evidence.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
OUTDIR="$HOME/klone-var/e11"
test -x "$PY" || { echo "Python venv puuttuu"; exit 1; }
test -f "$DB" || { echo "Päämuistin tietokantaa ei löytynyt"; exit 1; }
test -f "$ROOT/src/klone/limbo_evidence_review.py" || { echo "E11-moduuli puuttuu"; exit 1; }
mkdir -p "$OUTDIR"
cd "$ROOT"
echo "=== E11: offline-evidenssin rajat ja regressiotestit ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p "test_limbo_hypotheses.py" || exit 1
echo "=== Valitaan olemassa oleva oikea tutkimusjulkaisupari ==="
if [ "$#" -eq 2 ]; then
  FIRST="$1"
  SECOND="$2"
  [[ "$FIRST" =~ ^[1-9][0-9]*$ && "$SECOND" =~ ^[1-9][0-9]*$ ]] || {
    echo "Anna kaksi positiivista lähdemuistin ID:tä"; exit 1;
  }
elif [ "$#" -eq 0 ]; then
  PAIR="$(PYTHONPATH="$ROOT/src" "$PY" - <<'PY'
from pathlib import Path
from klone.limbo_source_dossiers import review_all
db=Path.home()/"klone"/"data"/"klone_mission_control.db"
rows=review_all(db,question="genetiikka")["dossiers"]
preferred=next((x for x in rows
                if x["source_comparison_type"]=="research_metadata_pair"
                and set(("graph","network")).issubset(x["common_non_generic_terms"])),None)
selected=preferred or next((x for x in rows
                            if x["source_comparison_type"]=="research_metadata_pair"),None)
if selected is None:
    raise SystemExit("Ei nykyisiä kahden tutkimuslähteen vertailupareja")
print(selected["source_a"]["event_id"],selected["source_b"]["event_id"])
PY
)" || exit 1
  read -r FIRST SECOND <<< "$PAIR"
else
  echo "Käyttö: bash scripts/klone-e11-phone.sh [FIRST_EVENT_ID SECOND_EVENT_ID]"
  exit 1
fi
STAMP="$(date +%Y%m%d-%H%M%S)"
TEMPLATE="$OUTDIR/owner-evidence-template-$FIRST-$SECOND-$STAMP.json"
echo "=== Luodaan VAIN pohja, ilman lähdetekstien hakua tai kirjoitusta päämuistiin ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_evidence_review \
  --klone-db "$DB" --question genetiikka \
  --prepare "$FIRST" "$SECOND" --output "$TEMPLATE"
echo "E11-pohja: $TEMPLATE"
echo "Kopioi itse sallitut lähdetekstit JSON-tiedoston sources.A/B.text-kenttiin."
echo "Anna kummallekin owner_supplied=true ja usage_rights_note."
echo "Kirjaa tarkat, vain kerran esiintyvät lainaukset annotations-kohtaan."
echo "Tarkista kopioimasi sisältö ennen paikallista --review-komentoa."
echo "Päämuisti, tutkimushuoneet ja palvelimet jätettiin ennalleen."
