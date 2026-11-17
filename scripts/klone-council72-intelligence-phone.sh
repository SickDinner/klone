#!/usr/bin/env bash
# KLONE Council72 Intelligence Bridge v1 — preview offline, live only by consent.
# Real live = exactly eight ring calls + one founder synthesis via OpenAI Responses.
# NEVER prints or commits API keys; never executes external model-suggested actions.
set -euo pipefail
set +x

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
WORK="$HOME/klone-var/e11"
MODE="${1:-preview}"
QUESTION="${2:-Mitä arXiv Atom -tiivistelmän ja PDF:n paikannuseroista voidaan päätellä, mikä jää vahvistamatta ja mikä on paras jatkotutkimuskysymys?}"
MODEL="${KLONE_COUNCIL72_MODEL:-gpt-6-luna}"

if [ "$MODE" != "preview" ] && [ "$MODE" != "live" ]; then
  echo "Käyttö: bash scripts/klone-council72-intelligence-phone.sh [preview|live] [julkinen tutkimuskysymys]"
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
if [ "$MODE" = "live" ]; then
  if [ "${KLONE_COUNCIL72_API_APPROVAL:-}" != "HYVAKSY_9_GPT_KUTSUA" ]; then
    echo "LIVE vaatii: export KLONE_COUNCIL72_API_APPROVAL=HYVAKSY_9_GPT_KUTSUA"
    exit 2
  fi
  if [ "${KLONE_COUNCIL72_CONFIRM_PUBLIC:-}" != "VAHVISTAN_JULKISUUDEN" ]; then
    echo "LIVE vaatii: export KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN"
    echo "Tarkista ensin E11.11-raportin quote_sample_for_owner_review -katkelmat."
    exit 2
  fi
  if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "OPENAI_API_KEY puuttuu. Syötä se paikalliseen ympäristöön, älä GitHubiin."
    exit 2
  fi
  echo "=== Omistaja hyväksyi 9 ulkoista API-kutsua ja julkisten katkelmien käsittelyn ==="
else
  echo "=== Council72 offline-esikatselu: EI verkkokutsuja, EI API-avainta ==="
fi

echo "E11.11 lähde: $(basename "$EVIDENCE")"
echo "Malli: $MODEL"
cd "$ROOT"
echo "=== 10 regressiotestiä, ei verkkokutsuja ==="
# Strip ALL paid-call credentials and approval flags from the unittest process.
# This is a second boundary independent of the test suite's HTTP mocks.
env -u OPENAI_API_KEY -u KLONE_COUNCIL72_API_APPROVAL \
    -u KLONE_COUNCIL72_CONFIRM_PUBLIC \
    PYTHONPATH="$ROOT/src" "$PY" -m unittest discover -s tests \
    -p test_council72_intelligence_bridge.py -v
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$HOME/klone-var/e11/council72-intelligence-$MODE-$STAMP-$$.json"
ARGS=(--evidence "$EVIDENCE" --question "$QUESTION" --output "$OUTPUT"
      --model "$MODEL")
if [ "$MODE" = "live" ]; then
  ARGS+=(--live --owner-confirms-public-data)
fi
echo "=== Council72 $MODE ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.council72_intelligence_bridge "${ARGS[@]}"
echo "=== Raportti: $OUTPUT ==="
if [ "$MODE" = "live" ]; then
  echo "Todelliset 9 mallikutsua suoritettu. Tarkista raportti ennen mitään jatkotoimia."
else
  echo "Ei verkkoa; erillinen live-hyväksyntä dokumentaation mukaan."
fi
