#!/usr/bin/env bash
# KLONE E11.11: re-verify E11.10 and compare the arXiv Atom abstract to local PDFs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
WORK="$HOME/klone-var/e11"
DB="$HOME/klone/data/klone_mission_control.db"
if [ "$#" -ne 2 ]; then
  echo "Käyttö: bash scripts/klone-e11-11-phone.sh A.pdf B.pdf"
  exit 2
fi
if [ "${KLONE_E11_11_OWNER_APPROVAL:-}" != "HYVAKSY_ABSTRAKTI_PDF" ]; then
  echo "Anna erillinen lupa paikalliseen Atom/PDF-vertailuun:"
  echo "export KLONE_E11_11_OWNER_APPROVAL=HYVAKSY_ABSTRAKTI_PDF"
  exit 2
fi
if [ ! -x "$PY" ] || [ ! -f "$DB" ]; then
  echo "KLONE Python tai kanoninen DB puuttuu"
  exit 1
fi
command -v pdfinfo >/dev/null && command -v pdftotext >/dev/null || {
  echo "Poppler-ohjelmat puuttuvat"
  exit 1
}
if [ ! -f "$1" ] || [ ! -f "$2" ]; then
  echo "Kummankin paikallisen PDF:n on oltava olemassa"
  exit 1
fi
if [ -z "${KLONE_E11_10_PDF_SHA_A:-}" ] || [ -z "${KLONE_E11_10_PDF_SHA_B:-}" ]; then
  echo "Ilmoita aiemmin kirjatut KLONE_E11_10_PDF_SHA_A/B -tarkisteet"
  exit 2
fi

mapfile -t INPUTS < <("$PY" - "$WORK" <<'PY'
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
def load(path):
    return json.loads(path.read_text(encoding="utf-8"))
def exact(pattern, fingerprint):
    paths = [p for p in sorted(root.glob(pattern))
             if load(p).get("report_sha256") == fingerprint]
    if not paths:
        raise SystemExit("E11.11: edeltäjäraporttia ei löydy: " + pattern)
    return paths[-1]

reports = sorted(root.glob("e11-10-pdf-sivupaikannus-*.json"))
if not reports:
    raise SystemExit("E11.10-raportti puuttuu")
pdf_report = reports[-1]
pdf = load(pdf_report)
fulltext = exact("e11-9-kokotekstivertailu-*.json",
                 pdf["e11_9_report_sha256"])
ft = load(fulltext)
cards = exact("e11-8-tarkistuskortit-*.json",
              ft["e11_8_report_sha256"])
comp = exact("e11-7-tiivistelmavertailu-*.json",
             load(cards)["e11_7_report_sha256"])
cc = load(comp)
queue = exact("e11-5-tarkistusjono-*.json", cc["e11_5_report_sha256"])
receipt = exact("e11-6-arxiv-vastaukset-*.json", cc["e11_6_report_sha256"])
quality = exact("e11-4-laatuauditointi-*.json", load(queue)["e11_4_report_sha256"])
q = load(quality)
proposals = exact("e11-2-ehdokkaat-*.json", q["e11_2_proposal_sha256"])
ledger = exact("e11-3-tarkistus-*.json", q["e11_3_ledger_sha256"])
selected = root / ("e11-3-konteksti-" +
                   ledger.name.removeprefix("e11-3-tarkistus-"))
if not selected.is_file():
    raise SystemExit("E11.3-konteksti puuttuu")
for role in ("A", "B"):
    print(root / (ft["sources"][role]["arxiv_id"] + ".txt"))
for path in (root / "e11-taytetty.json", proposals, selected, ledger,
             quality, queue, receipt, comp, cards, fulltext, pdf_report):
    print(path)
PY
)
if [ "${#INPUTS[@]}" -ne 13 ]; then
  echo "E11.11-lähdeketju puutteellinen"
  exit 1
fi
if [ ! -f "${INPUTS[0]}" ] || [ ! -f "${INPUTS[1]}" ]; then
  echo "E11.9:n kokotekstikopiot puuttuvat"
  exit 1
fi
cd "$ROOT"
echo "=== E11.11: turvallisuustestit ==="
PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
  -s tests -p test_limbo_abstract_pdf_diagnostics.py -v
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/e11-11-abstrakti-pdf-erot-$STAMP.json"
echo "=== E11.11: arXiv Atom / PDF -tekstipintojen erot ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.limbo_abstract_pdf_diagnostics \
  --klone-db "$DB" --pdf-a "$1" --pdf-b "$2" \
  --pdf-a-sha256 "$KLONE_E11_10_PDF_SHA_A" \
  --pdf-b-sha256 "$KLONE_E11_10_PDF_SHA_B" \
  --text-a "${INPUTS[0]}" --text-b "${INPUTS[1]}" \
  --original "${INPUTS[2]}" --proposals "${INPUTS[3]}" \
  --selected "${INPUTS[4]}" --ledger "${INPUTS[5]}" \
  --quality "${INPUTS[6]}" --queue "${INPUTS[7]}" \
  --receipt "${INPUTS[8]}" --comparison "${INPUTS[9]}" \
  --cards "${INPUTS[10]}" --fulltext "${INPUTS[11]}" \
  --pdf-report "${INPUTS[12]}" \
  --owner-approves-abstract-pdf --output "$OUTPUT"
echo "=== E11.11 valmis: $OUTPUT ==="
