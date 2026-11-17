#!/usr/bin/env bash
# KLONE E11.5 – replay five original private JSON sources into a read-only queue.
# Does not fetch research online, execute agents, restart services or write Memory Core.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
WORK="$HOME/klone-var/e11"
ORIGINAL="$WORK/e11-taytetty.json"
test -x "$PY" || { echo "KLONE-Python puuttuu"; exit 1; }
test -f "$DB" || { echo "Päämuistin DB puuttuu"; exit 1; }
test -f "$ORIGINAL" || { echo "Alkuperäinen E11-manifesti puuttuu"; exit 1; }
test -f "$ROOT/src/klone/limbo_evidence_verification_queue.py" || {
  echo "E11.5-moduuli puuttuu; hae uusin GitHub-commit"; exit 1;
}
if [ "$#" -eq 0 ]; then
  QUALITY="$("$PY" - <<'PY'
from pathlib import Path
root=Path.home()/"klone-var"/"e11"
files=sorted(root.glob("e11-4-laatuauditointi-*.json"))
if not files:
    raise SystemExit("E11.4-laatuauditointia ei löytynyt. Aja ensin E11.4.")
print(files[-1])
PY
)" || exit 1
elif [ "$#" -eq 1 ]; then
  QUALITY="$1"
else
  echo "Käyttö: bash scripts/klone-e11-5-phone.sh [E11.4_REPORT.json]"
  exit 2
fi
test -f "$QUALITY" || { echo "E11.4-laaturaportti puuttuu: $QUALITY"; exit 1; }
# Resolve all four earlier files by immutable report lineage, not by latest
# timestamp alone. E11.5 recomputes them against the actual canonical DB.
INPUTS="$("$PY" - "$QUALITY" <<'PY'
import json,sys
from pathlib import Path
root=Path.home()/"klone-var"/"e11"
quality=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
wanted_ledger=quality["e11_3_ledger_sha256"]
wanted_proposals=quality["e11_2_proposal_sha256"]
for file in sorted(root.glob("e11-3-tarkistus-*.json")):
    row=json.loads(file.read_text(encoding="utf-8"))
    if row.get("report_sha256")==wanted_ledger:
        suf=file.name[len("e11-3-tarkistus-"):]
        selected=root/("e11-3-konteksti-"+suf)
        if selected.is_file():
            break
else:
    raise SystemExit("E11.3:n vastaavaa tarkistus- ja hyväksyntäparia ei löydy")
for file in sorted(root.glob("e11-2-ehdokkaat-*.json")):
    row=json.loads(file.read_text(encoding="utf-8"))
    if row.get("report_sha256")==wanted_proposals:
        proposals=file
        break
else:
    raise SystemExit("E11.2:n vastaavaa ehdotusraporttia ei löydy")
print(proposals)
print(selected)
print(root/("e11-3-tarkistus-"+suf))
PY
)" || exit 1
PROPOSALS="$(printf '%s\n' "$INPUTS" | sed -n '1p')"
SELECTED="$(printf '%s\n' "$INPUTS" | sed -n '2p')"
LEDGER="$(printf '%s\n' "$INPUTS" | sed -n '3p')"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-5-tarkistusjono-$STAMP.json"
cd "$ROOT"
echo "=== E11.5: kohdennetut regressiotestit ennen analyysiä ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p test_limbo_hypotheses.py || exit 1
echo "=== E11.5: tarkistusjono, ei käynnistettyjä agentteja ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_evidence_verification_queue \
  --klone-db "$DB" --original "$ORIGINAL" \
  --proposals "$PROPOSALS" --selected "$SELECTED" \
  --ledger "$LEDGER" --quality "$QUALITY" \
  --output "$OUTPUT"
"$PY" - "$OUTPUT" <<'PY'
import json,sys
from pathlib import Path
report=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("Lähdepari:",*report["source_event_ids"])
print("Alkuperäistä tutkimusta odottavat tekstikohdat:",report["primary_source_checks_needed"])
print("Sivuun siirretyt otsikot/kysymykset/varoitukset:",report["deferred_non_evidence_context_count"])
print("Ehdotettuja neuvoston tarkistustehtäviä:",report["pending_council_task_proposals"])
print("Todellisia neuvoston tarkistuksia:",report["completed_council_reviews"])
print("Varmennettuja tieteellisiä tuloksia:",report["verified_scientific_results"])
print("Päämuistikirjoituksia:",report["authority"]["memory_write"])
for item in report["queue"]:
    print("  •",item["source"],item["quality_category"],
          "→ tarkistajat:",", ".join(str(t["member_id"]) for t in item["verification_tasks"]))
PY
echo "E11.5 valmis: $OUTPUT"
