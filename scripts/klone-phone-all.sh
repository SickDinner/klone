#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${KLONE_ROOT:-$HOME/klone-next}"
BRANCH="feat/web-os-cognition-lab-20261112"
PORT="${KLONE_PORT:-8001}"
FILES=(src/klone/main.py src/klone/cognition_core.py src/klone/cognition_api.py src/klone/cognition_memory.py src/klone/cognition_metrics.py src/klone/cognition_planner.py src/klone/cognition_learning.py src/klone/cognition_sweep.py src/klone/static/web_os_10.html src/klone/static/web_os_10.js tests/test_cognition_core.py tests/test_cognition_api.py tests/test_cognition_memory.py tests/test_cognition_metrics.py tests/test_cognition_planner.py tests/test_cognition_learning.py tests/test_cognition_sweep.py)
say(){ printf '\n[KLONE] %s\n' "$*"; }
die(){ echo "VIRHE: $*" >&2; exit 1; }
[[ -d "$ROOT/.git" && -x "$ROOT/.venv/bin/python" ]] || die "Asennusta ei löydy: $ROOT"
command -v git >/dev/null && command -v curl >/dev/null || die "git ja curl tarvitaan"
cd "$ROOT"
git fetch origin "$BRANCH" || die "GitHub-haku epäonnistui"
REF="refs/remotes/origin/$BRANCH"
git rev-parse --verify "$REF^{commit}" >/dev/null || die "Haaraa ei löydy"
for file in "${FILES[@]}"; do git cat-file -e "$REF:$file" || die "Puuttuu: $file"; done
BACKUP="$HOME/klone-backups/cognition-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP" "$HOME/klone-var"
say "Varmuuskopio: $BACKUP"
for file in "${FILES[@]}"; do
  if [[ -f "$file" ]]; then mkdir -p "$BACKUP/$(dirname "$file")"; cp -p "$file" "$BACKUP/$file"; fi
  mkdir -p "$(dirname "$file")"
  git show "$REF:$file" > "$file" || die "Asennus epäonnistui: $file"
done
say "Testataan kognitio"
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_cognition*.py' -v || die "Testit epäonnistuivat; varmuuskopio: $BACKUP"
say "Valitaan toimiva palvelinportti"
for candidate in "$PORT" 8002 8003; do
  BASE="http://127.0.0.1:$candidate"
  if curl -fsS --max-time 2 "$BASE/api/cognition/learn" -X POST -H 'Content-Type: application/json' -d '{"steps":2}' >/dev/null 2>&1; then
    PORT="$candidate"; say "Uusi API jo toiminnassa portissa $PORT"; break
  fi
  if curl -sS --max-time 2 "$BASE/" >/dev/null 2>&1; then
    say "Portti $candidate varattu vanhalle palvelimelle; ei pysäytetä sitä"
    continue
  fi
  say "Käynnistetään palvelin porttiin $candidate"
  nohup env PYTHONPATH="$ROOT/src" "$ROOT/.venv/bin/python" -m uvicorn klone.main:app --host 127.0.0.1 --port "$candidate" > "$HOME/klone-var/cognition-$candidate.log" 2>&1 < /dev/null &
  echo "$!" > "$HOME/klone-var/cognition-$candidate.pid"
  PORT="$candidate"
  for attempt in $(seq 1 25); do
    if curl -fsS --max-time 2 -X POST "$BASE/api/cognition/learn" -H 'Content-Type: application/json' -d '{"steps":2}' >/dev/null 2>&1; then break; fi
    sleep 1
  done
  if curl -fsS --max-time 3 -X POST "$BASE/api/cognition/learn" -H 'Content-Type: application/json' -d '{"steps":2}' >/dev/null 2>&1; then break; fi
  tail -35 "$HOME/klone-var/cognition-$candidate.log" || true
  die "Palvelin ei käynnistynyt; tarkista loki"
done
BASE="http://127.0.0.1:$PORT"
curl -fsS --max-time 10 -X POST "$BASE/api/cognition/learn" -H 'Content-Type: application/json' -d '{"steps":64,"seed":72}' > "$HOME/klone-var/learning-result.json" || die "API:n oppimiskoe epäonnistui"
curl -fsS --max-time 10 -X POST "$BASE/api/cognition/plan" -H 'Content-Type: application/json' -d '{"energy":0.8,"uncertainty":0.7}' > "$HOME/klone-var/planning-result.json" || die "API:n suunnittelukoe epäonnistui"
say "VALMIS: $BASE/static/web_os_10.html"
printf 'API: %s/docs\nTulokset: %s/klone-var/\nVarmuuskopio: %s\n' "$BASE" "$HOME" "$BACKUP"
