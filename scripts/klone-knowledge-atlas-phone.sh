#!/usr/bin/env bash
# KLONE Wikipedia Knowledge Atlas, Android Termux: no hidden network writes.
set -euo pipefail
set +x
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
ATLAS="$HOME/klone-var/knowledge-atlas"
MODE="${1:-status}"
LANGUAGE="${2:-fi}"
REQUESTS="${3:-2}"
MAX_MB="${KLONE_WIKIPEDIA_ATLAS_MAX_MB:-512}"
USER_CONTACT="${KLONE_WIKIPEDIA_CONTACT:-https://github.com/SickDinner/klone}"

if [ ! -x "$PY" ]; then
  echo "KLONEn Python puuttuu: $PY"
  exit 2
fi
case "$MAX_MB" in ''|*[!0-9]*) echo "Virheellinen megatavuraja"; exit 2;; esac
case "$REQUESTS" in ''|*[!0-9]*) echo "Virheellinen pyyntömäärä"; exit 2;; esac
if [ "$REQUESTS" -gt 12 ] || [ "$REQUESTS" -lt 1 ]; then
  echo "Yhdellä ajolla enintään 12 Wikimedia-API-pyyntöä"; exit 2
fi
mkdir -p "$ATLAS"
cd "$ROOT"
echo "=== KLONE KNOWLEDGE ATLAS ==="
echo "Komento: $MODE | Korpus: $(basename "$ATLAS")"
echo "Maksimikoko: $MAX_MB Mt | Git: $(git rev-parse --short HEAD)"

case "$MODE" in
  plan)
    PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas \
      --root "$ATLAS" plan
    ;;
  test)
    env -u OPENAI_API_KEY -u KLONE_COUNCIL72_API_APPROVAL \
        -u KLONE_COUNCIL72_DEBATE_APPROVAL \
        PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
        -s tests -p 'test_knowledge_atlas*.py' -v
    ;;
  status)
    PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas \
      --root "$ATLAS" --max-mb "$MAX_MB" status
    ;;
  member)
    MEMBER="${2:-24}"
    PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas \
      --root "$ATLAS" member "$MEMBER"
    ;;
  search)
    QUERY="${2:-tieteen historia}"
    MEMBER="${3:-}"
    if [ -n "$MEMBER" ] && [[ "$MEMBER" =~ ^[0-9]+$ ]]; then
      PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas \
        --root "$ATLAS" search "$QUERY" --member-id "$MEMBER"
    else
      PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas \
        --root "$ATLAS" search "$QUERY"
    fi
    ;;
  ring)
    RING="${2:-6}"
    QUERY="${3:-Mitä voidaan perustellusti tietää tämän tutkimuksen aiheesta?}"
    OUTPUT="$ATLAS/atlas-ring-${RING}-$(date +%Y%m%d-%H%M%S)-$$.json"
    PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas_bridge \
      --root "$ATLAS" --ring-id "$RING" \
      --question "$QUERY" --output "$OUTPUT"
    ;;
  collect)
    if [ "${KLONE_WIKIPEDIA_PUBLIC_FETCH_APPROVAL:-}" != \
         "HAE_JULKISIA_WIKIPEDIA_ARTIKKELEITA" ]; then
      echo "Verkkokeräys estetty. Hyväksyntä tarvitaan:"
      echo "export KLONE_WIKIPEDIA_PUBLIC_FETCH_APPROVAL=HAE_JULKISIA_WIKIPEDIA_ARTIKKELEITA"
      exit 2
    fi
    echo "=== Ulkoinen Wikipedia-haku, ei GPT-kutsuja ==="
    echo "Kieli $LANGUAGE, pyyntöjä $REQUESTS, tauko 2 sekuntia"
    PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas \
      --root "$ATLAS" --max-mb "$MAX_MB" collect \
      --allow-network --language "$LANGUAGE" \
      --requests "$REQUESTS" --delay 2 --contact "$USER_CONTACT"
    ;;
  import-dump)
    FILE="${2:?Käyttö: import-dump /path/file.xml.bz2 en 2000 0}"
    LANGUAGE="${3:-en}"
    LIMIT="${4:-500}"
    SKIP="${5:-0}"
    EXPECTED_SHA="${6:-}"
    echo "=== VAIN PAIKALLINEN WIKIMEDIA XML, EI VERKKOA ==="
    ARGS=(--input "$FILE" --language "$LANGUAGE"
      --max-pages "$LIMIT" --skip-pages "$SKIP")
    if [ -n "$EXPECTED_SHA" ]; then
      ARGS+=(--expected-sha256 "$EXPECTED_SHA")
    fi
    PYTHONPATH="$ROOT/src" "$PY" -m klone.knowledge_atlas \
      --root "$ATLAS" --max-mb "$MAX_MB" import-dump \
      "${ARGS[@]}"
    ;;
  *)
    echo "Käyttö: bash scripts/klone-knowledge-atlas-phone.sh [test|plan|status|member|search|ring|collect|import-dump]"
    exit 2
    ;;
esac
