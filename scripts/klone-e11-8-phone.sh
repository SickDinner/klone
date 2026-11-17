#!/usr/bin/env bash
# KLONE E11.8: replay eight private reports into unit-aware review cards.
# Offline only: no agent work, science approvals, service restart or DB writes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
WORK="$HOME/klone-var/e11"
ORIGINAL="$WORK/e11-taytetty.json"
test -x "$PY" || { echo "KLONE Python puuttuu"; exit 1; }
test -f "$DB" || { echo "Päämuistin tietokanta puuttuu"; exit 1; }
test -f "$ORIGINAL" || { echo "Alkuperäinen E11-manifesti puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_evidence_cards.py" || {
  echo "E11.8-koodia ei löydy. Hae uusi GitHub-versio."; exit 1;
}
if [ "$#" -gt 1 ]; then
  echo "Käyttö: bash scripts/klone-e11-8-phone.sh [E11.7_COMPARISON.json]"
  exit 2
fi
echo "=== E11.8: paikannetaan alkuperäinen kahdeksan asiakirjan ketju ==="
INPUTS="$("$PY" - "$WORK" "$ORIGINAL" "$@" <<'PY'
import json,sys
from pathlib import Path
folder=Path(sys.argv[1])
original=Path(sys.argv[2])
specific=sys.argv[3] if len(sys.argv)>3 else None

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def match(pattern,digest):
    for path in sorted(folder.glob(pattern)):
        if load(path).get("report_sha256")==digest:
            return path
    raise SystemExit("Raporttia ei löydy oikealla tarkisteella: "+pattern)

if specific:
    comp=Path(specific)
    if not comp.is_file():
        raise SystemExit("Puuttuva E11.7-tiedosto: "+str(comp))
else:
    candidates=sorted(folder.glob("e11-7-tiivistelmavertailu-*.json"))
    if not candidates:
        raise SystemExit("E11.7-raportti puuttuu. Aja ensin E11.7.")
    comp=candidates[-1]
data=load(comp)
queue=match("e11-5-tarkistusjono-*.json",data["e11_5_report_sha256"])
receipt=match("e11-6-arxiv-vastaukset-*.json",data["e11_6_report_sha256"])
q=load(queue)
quality=match("e11-4-laatuauditointi-*.json",q["e11_4_report_sha256"])
ql=load(quality)
proposals=match("e11-2-ehdokkaat-*.json",ql["e11_2_proposal_sha256"])
ledger=match("e11-3-tarkistus-*.json",ql["e11_3_ledger_sha256"])
suffix=ledger.name[len("e11-3-tarkistus-"):]
selected=folder/("e11-3-konteksti-"+suffix)
if not selected.is_file():
    raise SystemExit("E11.3-konseptihyväksyntä puuttuu: "+str(selected))
for path in (original,proposals,selected,ledger,quality,queue,receipt,comp):
    print(path)
PY
)" || exit 1
ORIGINAL="$(printf '%s\n' "$INPUTS" | sed -n '1p')"
PROPOSALS="$(printf '%s\n' "$INPUTS" | sed -n '2p')"
SELECTED="$(printf '%s\n' "$INPUTS" | sed -n '3p')"
LEDGER="$(printf '%s\n' "$INPUTS" | sed -n '4p')"
QUALITY="$(printf '%s\n' "$INPUTS" | sed -n '5p')"
QUEUE="$(printf '%s\n' "$INPUTS" | sed -n '6p')"
RECEIPT="$(printf '%s\n' "$INPUTS" | sed -n '7p')"
COMPARISON="$(printf '%s\n' "$INPUTS" | sed -n '8p')"
cd "$ROOT"
echo "=== E11.8: ajantasaiset turvallisuus- ja regressiotestit ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p test_limbo_hypotheses.py || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-8-tarkistuskortit-$STAMP.json"
echo "=== E11.8: luodaan yksikkötietoiset alkuperäislähteen tarkistuskortit ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_evidence_cards \
  --klone-db "$DB" --original "$ORIGINAL" \
  --proposals "$PROPOSALS" --selected "$SELECTED" --ledger "$LEDGER" \
  --quality "$QUALITY" --queue "$QUEUE" --receipt "$RECEIPT" \
  --comparison "$COMPARISON" --output "$OUTPUT"
"$PY" - "$OUTPUT" <<'PY'
import json,sys
from collections import Counter
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("Lähteet:",*r["source_event_ids"])
print("Tarkistuskortteja:",r["card_count"])
print("Keskeneräisiä Council72-tehtäviä:",r["proposed_pending_council_tasks"])
for priority,how_many in sorted(Counter(x["priority"] for x in r["cards"]).items()):
    print("  Prioriteetti",priority,":",how_many)
for card in r["cards"]:
    print(" •",card["source"],card["arxiv_id"],
          "prioriteetti",card["priority"],
          "numeromittoja",len(card["measured_quantities_in_local_quote"]),
          "saman yksikön osumia",len(card["unit_consistent_numeric_mentions_in_abstract"]))
print("Tieteellisesti vahvistettuja:",r["scientifically_verified_claims"])
print("Uusia verkkopyyntöjä:",r["new_network_requests"])
print("Muistikirjoituksia:",r["memory_write"])
PY
echo "=== E11.8 valmis: $OUTPUT ==="
