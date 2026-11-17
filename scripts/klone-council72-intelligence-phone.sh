#!/usr/bin/env bash
# Council72: preview 0 calls, probe 1, resume at most 8 new, live at most 9.
# Each accepted or received live response is checkpointed. No automatic retry.
set -euo pipefail
set +x

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
WORK="$HOME/klone-var/e11"
MODE="${1:-preview}"
QUESTION="${2:-Mitä arXiv Atom -tiivistelmän ja PDF:n paikannuseroista voidaan päätellä, mikä jää vahvistamatta ja mikä on paras jatkotutkimuskysymys?}"
MODEL="${KLONE_COUNCIL72_MODEL:-gpt-6-luna}"

if [ "$MODE" != "preview" ] && [ "$MODE" != "probe" ] && [ "$MODE" != "resume" ] && [ "$MODE" != "live" ]; then
  echo "Käyttö: bash scripts/klone-council72-intelligence-phone.sh [preview|probe|resume|live] [julkinen tutkimuskysymys]"
  exit 2
fi
if [ ! -x "$PY" ] || [ ! -d "$WORK" ]; then
  echo "KLONEn Python-virtuaaliympäristö tai E11-työhakemisto puuttuu"
  exit 1
fi
mapfile -t REPORTS < <(find "$WORK" -maxdepth 1 -type f \
  -name 'e11-11-abstrakti-pdf-erot-*.json' -print | sort)
if [ "${#REPORTS[@]}" -eq 0 ]; then
  echo "E11.11-raporttia ei löydy, eikä GPT:tä käynnistetä"
  exit 1
fi
EVIDENCE="${REPORTS[${#REPORTS[@]}-1]}"

SEED=""
if [ "$MODE" = "resume" ]; then
  mapfile -t PROBES < <(find "$WORK" -maxdepth 1 -type f \
    -name 'council72-intelligence-probe-*.json' -print | sort)
  if [ "${#PROBES[@]}" -eq 0 ]; then
    echo "Yhden kutsun onnistunut probe-raportti puuttuu: ei voi jatkaa"
    exit 2
  fi
  SEED="${PROBES[${#PROBES[@]}-1]}"
  echo "Aiempi maksullinen rinki 1: $(basename "$SEED")"
  echo "Ohjelma hyväksyy sen VAIN, jos raportin, mallin, kysymyksen,"
  echo "jäsenroolien, tutkimuskorttien ja pyyntötekstin tarkisteet täsmäävät."
fi

if [ "$MODE" != "preview" ]; then
  if [ "${KLONE_COUNCIL72_CONFIRM_PUBLIC:-}" != "VAHVISTAN_JULKISUUDEN" ]; then
    echo "Julkisen tutkimusaineiston siirto vaatii vahvistuksen:"
    echo "export KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN"
    exit 2
  fi
  case "$MODE" in
    probe)
      if [ "${KLONE_COUNCIL72_PROBE_APPROVAL:-}" != "HYVAKSY_1_GPT_KUTSU" ]; then
        echo "Vaaditaan: export KLONE_COUNCIL72_PROBE_APPROVAL=HYVAKSY_1_GPT_KUTSU"
        exit 2
      fi
      echo "=== Hyväksytty enintään YKSI uusi maksullinen kutsu ==="
      ;;
    resume)
      if [ "${KLONE_COUNCIL72_RESUME_APPROVAL:-}" != "HYVAKSY_ENINTAAN_8_GPT_KUTSUA" ]; then
        echo "Vaaditaan: export KLONE_COUNCIL72_RESUME_APPROVAL=HYVAKSY_ENINTAAN_8_GPT_KUTSUA"
        exit 2
      fi
      echo "=== Hyväksytty ENINTÄÄN KAHDEKSAN UUTTA maksullista kutsua ==="
      ;;
    live)
      if [ "${KLONE_COUNCIL72_API_APPROVAL:-}" != "HYVAKSY_9_GPT_KUTSUA" ]; then
        echo "Vaaditaan: export KLONE_COUNCIL72_API_APPROVAL=HYVAKSY_9_GPT_KUTSUA"
        exit 2
      fi
      echo "=== Hyväksytty ENINTÄÄN YHDEKSÄN UUTTA maksullista kutsua ==="
      ;;
  esac
  if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "OPENAI_API_KEY puuttuu. Älä lisää avainta lähdekoodiin."
    exit 2
  fi
else
  echo "=== Täysin verkoton preview; ei maksullisia API-kutsuja ==="
fi

echo "E11.11: $(basename "$EVIDENCE")"
echo "Malli: $MODEL"
cd "$ROOT"
echo "=== Offline-turvallisuustestit: EI API-avainta tai hyväksyntöjä ==="
env -u OPENAI_API_KEY -u KLONE_COUNCIL72_API_APPROVAL \
    -u KLONE_COUNCIL72_PROBE_APPROVAL \
    -u KLONE_COUNCIL72_RESUME_APPROVAL \
    -u KLONE_COUNCIL72_CONFIRM_PUBLIC \
    PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
    -s tests -p test_council72_intelligence_bridge.py -v

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/council72-intelligence-$MODE-$STAMP-$$.json"
ARGS=(--evidence "$EVIDENCE" --question "$QUESTION" --output "$OUTPUT" --model "$MODEL")

if [ "$MODE" = "resume" ]; then
  # Deterministic private checkpoint location: identical evidence+probe+
  # question+model resumes the same session without duplicate API requests.
  SESSION_ID="$("$PY" - "$EVIDENCE" "$SEED" "$QUESTION" "$MODEL" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys
evidence, seed, question, model = sys.argv[1:]
h = sha256()
for path in (evidence, seed):
    h.update(sha256(Path(path).read_bytes()).digest())
for value in (question, model):
    h.update(value.encode("utf-8"))
print(h.hexdigest()[:24])
PY
)"
  CHECKPOINT_DIR="$WORK/council72-sessions/resume-$SESSION_ID"
  echo "=== Tarkistuspisteet: $CHECKPOINT_DIR ==="
  ARGS+=(--live --owner-confirms-public-data \
    --resume-from-probe "$SEED" --checkpoint-dir "$CHECKPOINT_DIR")
elif [ "$MODE" = "live" ]; then
  CHECKPOINT_DIR="$WORK/council72-sessions/live-$STAMP-$$"
  echo "=== Uusi istunto; tarkistuspisteet: $CHECKPOINT_DIR ==="
  ARGS+=(--live --owner-confirms-public-data \
    --checkpoint-dir "$CHECKPOINT_DIR")
elif [ "$MODE" = "probe" ]; then
  ARGS+=(--probe --owner-confirms-public-data)
fi

echo "=== Council72 $MODE ==="
PYTHONPATH="$ROOT/src" "$PY" -m klone.council72_intelligence_bridge "${ARGS[@]}"
echo "=== Raportti: $OUTPUT ==="
if [ "$MODE" = "resume" ]; then
  echo "Koko 72 roolin synteesi valmistui: rinki 1 käytettiin uudelleen, muille suoritettiin puuttuvat kutsut."
elif [ "$MODE" = "live" ]; then
  echo "Yhdeksän neuvostoanalyysiä valmistui. Tarkista tulos."
elif [ "$MODE" = "probe" ]; then
  echo "Yksi mallikutsu valmistui; muita rinkejä ei ajettu."
else
  echo "Esikatselu valmis; ei verkkokutsuja."
fi
