#!/usr/bin/env bash
# KLONE E11.9 – offline analysis of two owner-supplied UTF-8 source texts.
# Never downloads PDFs, runs Council72, modifies memory or restarts services.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
WORK="$HOME/klone-var/e11"
DB="$HOME/klone/data/klone_mission_control.db"

if [ "$#" -ne 2 ]; then
  echo "Käyttö: bash scripts/klone-e11-9-phone.sh SOURCE_A.txt SOURCE_B.txt"
  echo "A/B:n arXiv-versiot katsotaan kanonisesta E11.8-raportista."
  exit 2
fi
if [ "${KLONE_E11_9_OWNER_APPROVAL:-}" != "HYVAKSY_KOKOTEKSTI" ]; then
  echo "E11.9 vaatii erillisen paikallisen tekstin hyväksynnän:"
  echo "export KLONE_E11_9_OWNER_APPROVAL=HYVAKSY_KOKOTEKSTI"
  exit 2
fi
if [ -z "${KLONE_E11_9_RIGHTS_A:-}" ] || [ -z "${KLONE_E11_9_RIGHTS_B:-}" ]; then
  echo "Anna myös KLONE_E11_9_RIGHTS_A ja KLONE_E11_9_RIGHTS_B (käyttöoikeuksien kuvaus)."
  exit 2
fi
test -x "$PY" || { echo "KLONE Python puuttuu"; exit 1; }
test -f "$DB" || { echo "KLONE Memory Core puuttuu"; exit 1; }
test -f "$1" || { echo "Lähdeteksti A puuttuu"; exit 1; }
test -f "$2" || { echo "Lähdeteksti B puuttuu"; exit 1; }
test -f "$WORK/e11-taytetty.json" || { echo "E11-manifesti puuttuu"; exit 1; }

echo "=== E11.9: paikannetaan muuttumaton E11.1–E11.8 lähdeketju ==="
mapfile -t INPUTS < <("$PY" - "$WORK" <<'PY'
import json
from pathlib import Path
import sys

folder = Path(sys.argv[1])

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def find(pattern, digest):
    matching = [p for p in sorted(folder.glob(pattern))
                if load(p).get("report_sha256") == digest]
    if not matching:
        raise SystemExit("Lähdeketjun SHA-osuma puuttuu: " + pattern)
    return matching[-1]

candidates = sorted(folder.glob("e11-8-tarkistuskortit-*.json"))
if not candidates:
    raise SystemExit("E11.8-raportti puuttuu")
cards = candidates[-1]
card_obj = load(cards)
comparison = find("e11-7-tiivistelmavertailu-*.json",
                  card_obj["e11_7_report_sha256"])
comp_obj = load(comparison)
queue = find("e11-5-tarkistusjono-*.json", comp_obj["e11_5_report_sha256"])
receipt = find("e11-6-arxiv-vastaukset-*.json", comp_obj["e11_6_report_sha256"])
quality = find("e11-4-laatuauditointi-*.json",
               load(queue)["e11_4_report_sha256"])
quality_obj = load(quality)
proposals = find("e11-2-ehdokkaat-*.json",
                 quality_obj["e11_2_proposal_sha256"])
ledger = find("e11-3-tarkistus-*.json",
              quality_obj["e11_3_ledger_sha256"])
selected = folder / ("e11-3-konteksti-" +
                     ledger.name.removeprefix("e11-3-tarkistus-"))
if not selected.is_file():
    raise SystemExit("E11.3 omistajan hyväksyntä puuttuu")
for role in ("A", "B"):
    ids = {c["arxiv_id"] for c in card_obj["cards"] if c["source"] == role}
    if len(ids) != 1:
        raise SystemExit("E11.8 ei yksiselitteisesti sido lähdettä " + role)
    print(next(iter(ids)))
for path in (folder / "e11-taytetty.json", proposals, selected, ledger,
             quality, queue, receipt, comparison, cards):
    print(path)
PY
)
if [ "${#INPUTS[@]}" -ne 11 ]; then
  echo "E11.9: lähteiden paikannus epäonnistui"
  exit 1
fi
echo "A = ${INPUTS[0]}"
echo "B = ${INPUTS[1]}"
echo "Varmistathan, että antamasi A/B-tekstit ovat juuri näiden versioiden tekstejä."

cd "$ROOT"
echo "=== E11.9: fail-closed regressiotestit ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover -s tests -p test_limbo_fulltext_review.py -v

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-9-kokotekstivertailu-$STAMP.json"
echo "=== E11.9: offline tekstivertailu ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_fulltext_review \
  --klone-db "$DB" \
  --source-a-file "$1" --source-b-file "$2" \
  --source-a-id "${INPUTS[0]}" --source-b-id "${INPUTS[1]}" \
  --rights-note-a "$KLONE_E11_9_RIGHTS_A" \
  --rights-note-b "$KLONE_E11_9_RIGHTS_B" \
  --owner-confirms-local-text \
  --original "${INPUTS[2]}" --proposals "${INPUTS[3]}" \
  --selected "${INPUTS[4]}" --ledger "${INPUTS[5]}" \
  --quality "${INPUTS[6]}" --queue "${INPUTS[7]}" \
  --receipt "${INPUTS[8]}" --comparison "${INPUTS[9]}" \
  --cards "${INPUTS[10]}" --output "$OUTPUT"
echo "=== E11.9 valmis: $OUTPUT ==="
