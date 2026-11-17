#!/usr/bin/env bash
# Council72 Quality + Debate + Public Evidence Tools, Android/Termux.
# audit / preview / tools: ZERO network, ZERO paid tokens.
# debate-live: max three explicit GPT calls; checkpoints prevent rebilling.
set -euo pipefail
set +x

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/klone-next/.venv/bin/python"
WORK="$HOME/klone-var/e11"
MODE="${1:-audit}"
MODEL="${KLONE_COUNCIL72_MODEL:-gpt-6-luna}"

if [ "$MODE" != "audit" ] && [ "$MODE" != "debate-preview" ] && \
   [ "$MODE" != "tools" ] && [ "$MODE" != "debate-live" ]; then
  echo "Käyttö: bash scripts/klone-council72-quality-phone.sh [audit|debate-preview|tools|debate-live]"
  exit 2
fi
if [ ! -x "$PY" ] || [ ! -d "$WORK" ]; then
  echo "KLONE-venv tai E11-työhakemisto puuttuu"
  exit 2
fi

mapfile -t REPORTS < <(find "$WORK" -maxdepth 1 -type f \
  -name 'council72-intelligence-resume-*.json' -print | sort)
mapfile -t EVIDENCE < <(find "$WORK" -maxdepth 1 -type f \
  -name 'e11-11-abstrakti-pdf-erot-*.json' -print | sort)
if [ "${#REPORTS[@]}" -eq 0 ] || [ "${#EVIDENCE[@]}" -eq 0 ]; then
  echo "Vaaditaan valmis Council72 resume -raportti ja E11.11 lähdepaketti"
  exit 2
fi
REPORT="${REPORTS[${#REPORTS[@]}-1]}"
SOURCE="${EVIDENCE[${#EVIDENCE[@]}-1]}"
cd "$ROOT"
echo "=== Raportti: $(basename "$REPORT") ==="
echo "=== Julkinen näyttö: $(basename "$SOURCE") ==="

echo "=== Offline-regressiotestit (avaimet ja hyväksynnät EIVÄT siirry testeihin) ==="
env -u OPENAI_API_KEY -u KLONE_COUNCIL72_API_APPROVAL \
    -u KLONE_COUNCIL72_PROBE_APPROVAL \
    -u KLONE_COUNCIL72_RESUME_APPROVAL \
    -u KLONE_COUNCIL72_DEBATE_APPROVAL \
    -u KLONE_COUNCIL72_CONFIRM_PUBLIC \
    PYTHONPATH="$ROOT/src" "$PY" -m unittest discover \
    -s tests -p 'test_council72_quality_debate.py' -v

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT="$WORK/council72-quality-$MODE-$STAMP-$$.json"
case "$MODE" in
  audit)
    echo "=== 72 roolin laatuauditointi: offline ==="
    PYTHONPATH="$ROOT/src" "$PY" -m klone.council72_quality_lab \
      --report "$REPORT" --evidence "$SOURCE" --mode assess \
      --output "$OUTPUT"
    ;;
  debate-preview)
    echo "=== Neuvoston väittelyaineisto: offline ==="
    # Run the real API serializer preflight without sending any HTTP
    # request; report includes exact stage-one UTF-8 byte size and profile.
    PYTHONPATH="$ROOT/src" "$PY" -m klone.council72_debate \
      --report "$REPORT" --evidence "$SOURCE" --model "$MODEL" \
      --output "$OUTPUT"
    ;;
  tools)
    echo "=== Vain julkisen E11.11-aineiston sallittu lukutoiminto ==="
    PYTHONPATH="$ROOT/src" "$PY" -m klone.council72_quality_lab \
      --evidence "$SOURCE" --mode tool \
      --tool discrepancy_counts --output "$OUTPUT"
    ;;
  debate-live)
    if [ "${KLONE_COUNCIL72_CONFIRM_PUBLIC:-}" != "VAHVISTAN_JULKISUUDEN" ]; then
      echo "Tarkistettujen julkisten aineistojen siirtohyväksyntä puuttuu"
      exit 2
    fi
    if [ "${KLONE_COUNCIL72_DEBATE_APPROVAL:-}" != "HYVAKSY_3_GPT_KUTSUA" ]; then
      echo "Vaaditaan: export KLONE_COUNCIL72_DEBATE_APPROVAL=HYVAKSY_3_GPT_KUTSUA"
      exit 2
    fi
    if [ -z "${OPENAI_API_KEY:-}" ]; then
      echo "OPENAI_API_KEY puuttuu, älä liitä avainta GitHubiin"
      exit 2
    fi
    # Stable session ID for identical full report bytes+model, to replay
    # already-received answers without automatically paying twice.
    SESSION="$("$PY" - "$REPORT" "$SOURCE" "$MODEL" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys
h=sha256()
for x in sys.argv[1:3]:
    h.update(sha256(Path(x).read_bytes()).digest())
h.update(sys.argv[3].encode())
print(h.hexdigest()[:24])
PY
)"
    OLD_DIR="$WORK/council72-sessions/debate-$SESSION"
    # Do not silently rebill responses that an old prompt version already
    # received. A previously empty directory (preflight failure) is safe.
    if [ -d "$OLD_DIR" ] && \
       find "$OLD_DIR" -maxdepth 1 -type f \
         \( -name '*-accepted.json' -o -name '*-received-unverified.json' \) \
         -print -quit | grep -q .; then
      echo "VANHAN debate-v1-istunnon vastauksia löytyy: $OLD_DIR"
      echo "Pysäytetty varmuuden vuoksi; ensin on tarkistettava maksetut vastaukset."
      exit 2
    fi
    DIR="$WORK/council72-sessions/debate-v2-$SESSION"
    echo "=== Enintään kolme maksullista GPT-kutsua: vastaväite, puolustus, yhteenveto ==="
    echo "=== Tarkistuspisteet: $DIR ==="
    PYTHONPATH="$ROOT/src" "$PY" -m klone.council72_debate \
      --report "$REPORT" --evidence "$SOURCE" --model "$MODEL" \
      --output "$OUTPUT" --live --owner-confirms-public-data \
      --checkpoint-dir "$DIR"
    ;;
esac

echo "=== Tulos: $OUTPUT ==="
"$PY" - "$OUTPUT" <<'PY'
import json
import sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("Tyyppi:",r["kind"])
print("Uudet API-kutsut:",r.get("model_api_requests_performed",0))
print("Muistikirjoitukset:",r["memory_write"])
if "role_count" in r:
    print("Arvioituja rooleja:",r["role_count"])
    print("Lexikaalisesti samankaltaisia pareja:",len(r["likely_lexical_overlaps"]))
    print("Lähdekorttien viittauskattavuus:",r["citation_coverage"])
if "request_preflight" in r:
    p = r["request_preflight"]
    print("Mallisyötteen preflight:", p["cross_examination_body_bytes"],
          "/", p["hard_request_limit_bytes"], "tavua")
    print("Mukana asiantuntijarooleja:", p["retained_member_statements"])
if "debate_turns" in r:
    print("Väittelykierroksia:",len(r["debate_turns"]))
    print("Päätös:",r["debate_turns"][-1]["answer"]["decision"])
    print("Pyyntöjen koot:", [v["request_bytes"] for v in r["request_size_audit"]])
PY
