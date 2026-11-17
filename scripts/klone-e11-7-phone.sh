#!/usr/bin/env bash
# KLONE E11.7: offline comparison of verified 26/24 arXiv Atom abstracts
# against the owner-approved E11.5 review queue.
# No network calls, source downloads, agent execution or Memory Core writes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
WORK="$HOME/klone-var/e11"
ORIGINAL="$WORK/e11-taytetty.json"
test -x "$PY" || { echo "KLONE-Python puuttuu"; exit 1; }
test -f "$DB" || { echo "Päämuisti puuttuu"; exit 1; }
test -f "$ORIGINAL" || { echo "Alkuperäinen täytetty E11-manifesti puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_arxiv_abstract_compare.py" || {
  echo "E11.7-moduuli puuttuu. Hae uusi GitHub-versio."; exit 1;
}
if [ "$#" -gt 2 ]; then
  echo "Käyttö: bash scripts/klone-e11-7-phone.sh [E11.5_QUEUE.json E11.6_RECEIPT.json]"
  exit 2
fi
echo "=== E11.7: ratkaise nykyinen tutkimusketju alkuperäistarkisteista ==="
INPUTS="$("$PY" - "$WORK" "$ORIGINAL" "$@" <<'PY'
import json,sys
from pathlib import Path
folder=Path(sys.argv[1])
original=Path(sys.argv[2])
given=sys.argv[3:]
def pick(pattern,explicit=None):
    if explicit:
        path=Path(explicit)
        if not path.is_file():
            raise SystemExit("Puuttuva tiedosto: "+str(path))
        return path
    options=sorted(folder.glob(pattern))
    if not options:
        raise SystemExit("Raporttia ei löydy: "+pattern)
    return options[-1]
def load(p):
    return json.loads(p.read_text(encoding="utf-8"))
queue=pick("e11-5-tarkistusjono-*.json",given[0] if len(given)>0 else None)
receipt=pick("e11-6-arxiv-vastaukset-*.json",given[1] if len(given)>1 else None)
q=load(queue)
r=load(receipt)
if (q.get("source_event_ids")!=r.get("source_event_ids")
    or q.get("source_snapshot_sha256")!=r.get("source_snapshot_sha256")):
    raise SystemExit("E11.5 ja E11.6 ovat eri tutkimuspareista tai muistiversioista")
def find_by_sha(pattern,digest):
    for path in sorted(folder.glob(pattern)):
        if load(path).get("report_sha256")==digest:
            return path
    raise SystemExit("Vaadittu raportti puuttuu tai SHA ei täsmää: "+pattern)
quality=find_by_sha("e11-4-laatuauditointi-*.json",q["e11_4_report_sha256"])
ql=load(quality)
proposals=find_by_sha("e11-2-ehdokkaat-*.json",ql["e11_2_proposal_sha256"])
ledger=find_by_sha("e11-3-tarkistus-*.json",ql["e11_3_ledger_sha256"])
suffix=ledger.name[len("e11-3-tarkistus-"):]
selected=folder/("e11-3-konteksti-"+suffix)
if not selected.is_file():
    raise SystemExit("E11.3-hyväksyntä ei löydy: "+str(selected))
for path in (original,proposals,selected,ledger,quality,queue,receipt):
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
cd "$ROOT"
echo "=== E11.7: regressiotestit ilman verkkohakua ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p test_limbo_hypotheses.py || exit 1
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-7-tiivistelmavertailu-$STAMP.json"
echo "=== E11.7: arXiv-tiivistelmät vastaan paikalliset selostuskatkelmat ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_arxiv_abstract_compare \
  --klone-db "$DB" --original "$ORIGINAL" \
  --proposals "$PROPOSALS" --selected "$SELECTED" --ledger "$LEDGER" \
  --quality "$QUALITY" --queue "$QUEUE" --receipt "$RECEIPT" \
  --output "$OUTPUT"
"$PY" - "$OUTPUT" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("Lähteet:",*r["source_event_ids"])
print("ArXiv-tiivistelmiä:",r["abstracts_from_arxiv_atom"])
print("Verrattuja kontekstikatkelmia:",r["local_quotes_compared"])
for label,count in sorted(r["comparison_counts"].items()):
    print("  ",label,":",count)
print("Tieteellisesti vahvistettuja väitteitä:",r["confirmed_scientific_claims"])
print("Kokotekstejä tarkistettu:",r["full_text_papers_checked"])
print("Uusia verkkopyyntöjä:",r["new_network_requests"])
print("Päämuistikirjoituksia:",r["memory_write"])
PY
echo "E11.7 valmis: $OUTPUT"
