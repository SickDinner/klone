#!/usr/bin/env bash
# Council72 Intelligence Bridge: preview offline; probe only 1 call; live 9 calls.
# No automatic retry or resume. Approval and billing scope are explicit.
set -euo pipefail
set +x
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
WORK="$HOME/klone-var/e11"
MODE="${1:-preview}"
QUESTION="${2:-Mitä arXiv Atom -tiivistelmän ja PDF:n paikannuseroista voidaan päätellä, mikä jää vahvistamatta ja mikä on paras jatkotutkimuskysymys?}"
MODEL="${KLONE_COUNCIL72_MODEL:-gpt-6-luna}"

if [ "$MODE" != "preview" ] && [ "$MODE" != "probe" ] && [ "$MODE" != "live" ]; then
  echo "Käyttö: bash scripts/klone-council72-intelligence-phone.sh [preview|probe|live] [julkinen tutkimuskysymys]"
  exit 2
fi
if [ ! -x "$PY" ]; then
  echo "KLONEn virtuaaliympäristö puuttuu: $PY"
  exit 1
fi
if [ ! -d "$WORK" ]; then
  echo "E11-työhakemisto puuttuu: $WORK"
  exit 1
fi
mapfile -t REPORTS < <(find "$WORK" -maxdepth 1 -type f \
  -name 'e11-11-abstrakti-pdf-erot-*.json' -print | sort)
if [ "${#REPORTS[@]}" -eq 0 ]; then
  echo "E11.11-raportti puuttuu; aja ensin E11.11"
  exit 1
fi
EVIDENCE="${REPORTS[${#REPORTS[@]}-1]}"

if [ "$MODE" != "preview" ]; then
  if [ "${KLONE_COUNCIL72_CONFIRM_PUBLIC:-}" != "VAHVISTAN_JULKISUUDEN" ]; then
    echo "Julkisten katkelmien siirron vahvistus puuttuu:"
    echo "export KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN"
    exit 2
  fi
  if [ "$MODE" = "probe" ]; then
    if [ "${KLONE_COUNCIL72_PROBE_APPROVAL:-}" != "HYVAKSY_1_GPT_KUTSU" ]; then
      echo "PROBE vaatii: export KLONE_COUNCIL72_PROBE_APPROVAL=HYVAKSY_1_GPT_KUTSU"
      exit 2
    fi
    echo "=== Omistaja hyväksyi YHDEN maksullisen GPT-koekutsun ==="
  elif [ "${KLONE_COUNCIL72_API_APPROVAL:-}" != "HYVAKSY_9_GPT_KUTSUA" ]; then
    echo "LIVE vaatii: export KLONE_COUNCIL72_API_APPROVAL=HYVAKSY_9_GPT_KUTSUA"
    exit 2
  else
    echo "=== Omistaja hyväksyi yhdeksän maksullista GPT-kutsua ==="
  fi
  if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "OPENAI_API_KEY puuttuu. Älä kopioi avainta GitHubiin."
    exit 2
  fi
else
  echo "=== Council72 offline-esikatselu: ei API-kutsuja ==="
fi

echo "E11.11 lähde: $(basename "$EVIDENCE")"
echo "Malli: $MODEL"
cd "$ROOT"
echo "=== Offline-regressiotestit; API-avain ja live-hyväksynnät POISTETTU testiympäristöstä ==="
env -u OPENAI_API_KEY -u KLONE_COUNCIL72_API_APPROVAL \
    -u KLONE_COUNCIL72_PROBE_APPROVAL -u KLONE_COUNCIL72_CONFIRM_PUBLIC \
    PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
    -s tests -p test_council72_intelligence_bridge.py -v

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/council72-intelligence-$MODE-$STAMP-$$.json"
ARGS=(--evidence "$EVIDENCE" --question "$QUESTION" --output "$OUTPUT" --model "$MODEL")
if [ "$MODE" = "live" ]; then
  ARGS+=(--live --owner-confirms-public-data)
elif [ "$MODE" = "probe" ]; then
  ARGS+=(--probe --owner-confirms-public-data)
fi

echo "=== Council72 $MODE ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.council72_intelligence_bridge "${ARGS[@]}"
echo "=== Raportti: $OUTPUT ==="
if [ "$MODE" = "live" ]; then
  echo "Yhdeksän kutsua onnistui; tarkista raportti. Ei ulkoisia toimia."
elif [ "$MODE" = "probe" ]; then
  echo "Yksi GPT-koekutsu onnistui; muuta neuvostoa EI käynnistetty."
else
  echo "Ei verkkoa; seuraava vaihe erillisen luvan vaativa yhden kutsun probe."
fi
