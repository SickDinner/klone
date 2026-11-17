#!/usr/bin/env bash
# KLONE E11.2: propose source-anchored reviewer tasks from owner-approved E11 text.
# This script does NOT run the 72 agents, vote, write KLONE memory or fetch sources.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
DB="$HOME/klone/data/klone_mission_control.db"
WORK="$HOME/klone-var/e11"
INPUT="$WORK/e11-taytetty.json"
if [ "$#" -ge 1 ]; then INPUT="$1"; fi
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-2-ehdokkaat-$STAMP.json"
test -x "$PY" || { echo "KLONE-Python ei löydy: $PY"; exit 1; }
test -f "$ROOT/src/klone/limbo_evidence_candidates.py" || {
  echo "E11.2-moduuli puuttuu, päivitä GitHub-haara"; exit 1;
}
test -f "$DB" || { echo "Pää-KLONEn alkuperäinen tietokanta puuttuu"; exit 1; }
test -f "$INPUT" || { echo "Täytetty E11-lähdemanifesti puuttuu: $INPUT"; exit 1; }
mkdir -p "$WORK"
cd "$ROOT"
echo "=== KLONE E11.2: tarkista kohdennetut E7–E11.2-regressiot ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s "$ROOT/tests" -p test_limbo_hypotheses.py || exit 1
echo "=== KLONE E11.2: ehdota vain perustelemattomia arviointitehtäviä ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_evidence_candidates \
  --klone-db "$DB" --manifest "$INPUT" \
  --per-source-limit 8 --output "$OUTPUT"
"$PY" - "$OUTPUT" <<'PY'
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text())
print("Lähdepari:",*r["source_event_ids"])
print("Alustavia tarkistusehdokkaita:",r["candidate_count"])
for item in r["candidates"]:
    print("Lähde",item["source"],"•",item["topic_for_review"],
          "• neuvoston jäsen",item["proposed_reviewer"]["member_id"],
          "• keskeneräinen")
print("Varsinaisia neuvoston tarkistuksia:",r["council_completed_reviews"])
print("Tieteellisesti vahvistettu:",r["authority"]["scientific_truth_verified"])
print("Päämuistiin kirjoitettu:",r["authority"]["memory_write"])
PY
echo "=== Valmis: $OUTPUT ==="
