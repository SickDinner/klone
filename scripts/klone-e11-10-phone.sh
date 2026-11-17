#!/usr/bin/env bash
# KLONE E11.10: owner-authorized offline PDF page localization, no network.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
WORK="$HOME/klone-var/e11"
DB="$HOME/klone/data/klone_mission_control.db"

if [ "$#" -ne 2 ]; then
  echo "Käyttö: bash scripts/klone-e11-10-phone.sh SOURCE_A.pdf SOURCE_B.pdf"
  exit 2
fi
if [ "${KLONE_E11_10_OWNER_APPROVAL:-}" != "HYVAKSY_PDF_SIVUT" ]; then
  echo "Omistajan erillinen PDF-tarkistuslupa puuttuu:"
  echo "export KLONE_E11_10_OWNER_APPROVAL=HYVAKSY_PDF_SIVUT"
  exit 2
fi
if [ ! -x "$PY" ] || [ ! -f "$DB" ]; then
  echo "KLONE Python tai päämuistin tietokanta puuttuu"
  exit 1
fi
command -v pdfinfo >/dev/null && command -v pdftotext >/dev/null || {
  echo "Asenna Poppler: pkg install poppler"
  exit 1
}
test -f "$1" && test -f "$2" || {
  echo "Jompikumpi alkuperäis-PDF puuttuu"
  exit 1
}
test -n "${KLONE_E11_10_PDF_SHA_A:-}" && test -n "${KLONE_E11_10_PDF_SHA_B:-}" || {
  echo "Ilmoita odotetut PDF-tarkisteet ympäristömuuttujissa:"
  echo "KLONE_E11_10_PDF_SHA_A ja KLONE_E11_10_PDF_SHA_B"
  exit 2
}

echo "=== E11.10: kootaan E11.1–E11.9 tarkisteketju ==="
mapfile -t INPUTS < <("$PY" - "$WORK" <<'PY'
import json, sys
from pathlib import Path
folder = Path(sys.argv[1])

def load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def find(pattern, key):
    found = [p for p in sorted(folder.glob(pattern))
             if load(p).get("report_sha256") == key]
    if not found:
        raise SystemExit("E11.10: tarvittava ketjutarkiste puuttuu: " + pattern)
    return found[-1]

reports = sorted(folder.glob("e11-9-kokotekstivertailu-*.json"))
if not reports:
    raise SystemExit("E11.9-raporttia ei ole")
fulltext = reports[-1]
ft = load(fulltext)
cards = find("e11-8-tarkistuskortit-*.json", ft["e11_8_report_sha256"])
comp = find("e11-7-tiivistelmavertailu-*.json", load(cards)["e11_7_report_sha256"])
c = load(comp)
queue = find("e11-5-tarkistusjono-*.json", c["e11_5_report_sha256"])
receipt = find("e11-6-arxiv-vastaukset-*.json", c["e11_6_report_sha256"])
quality = find("e11-4-laatuauditointi-*.json", load(queue)["e11_4_report_sha256"])
q = load(quality)
proposals = find("e11-2-ehdokkaat-*.json", q["e11_2_proposal_sha256"])
ledger = find("e11-3-tarkistus-*.json", q["e11_3_ledger_sha256"])
selected = folder / ("e11-3-konteksti-" +
                     ledger.name.removeprefix("e11-3-tarkistus-"))
if not selected.is_file():
    raise SystemExit("E11.3-konteksti puuttuu")
for role in ("A", "B"):
    print(folder / (ft["sources"][role]["arxiv_id"] + ".txt"))
for p in (folder / "e11-taytetty.json", proposals, selected, ledger,
          quality, queue, receipt, comp, cards, fulltext):
    print(p)
PY
)
if [ "${#INPUTS[@]}" -ne 12 ]; then
  echo "E11.10: ketjupaikannus ei onnistunut"
  exit 1
fi
test -f "${INPUTS[0]}" && test -f "${INPUTS[1]}" || {
  echo "E11.9:n lähdetekstit puuttuvat"
  exit 1
}

echo "=== E11.10: regressiotestit ==="
cd "$ROOT"
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s tests -p test_limbo_pdf_page_locator.py -v

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-10-pdf-sivupaikannus-$STAMP.json"
echo "=== E11.10: PDF-tarkisteet, tekstikopio ja sivupaikannus ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_pdf_page_locator \
  --klone-db "$DB" \
  --pdf-a "$1" --pdf-b "$2" \
  --pdf-a-sha256 "$KLONE_E11_10_PDF_SHA_A" \
  --pdf-b-sha256 "$KLONE_E11_10_PDF_SHA_B" \
  --text-a "${INPUTS[0]}" --text-b "${INPUTS[1]}" \
  --original "${INPUTS[2]}" --proposals "${INPUTS[3]}" \
  --selected "${INPUTS[4]}" --ledger "${INPUTS[5]}" \
  --quality "${INPUTS[6]}" --queue "${INPUTS[7]}" \
  --receipt "${INPUTS[8]}" --comparison "${INPUTS[9]}" \
  --cards "${INPUTS[10]}" --fulltext "${INPUTS[11]}" \
  --owner-approves-local-pdf --output "$OUTPUT"
echo "=== E11.10 valmis: $OUTPUT ==="
