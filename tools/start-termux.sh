#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Local-only Android profile. Never enable debug mode by default.
export KLONE_ENV=local
export KLONE_OWNER_DEBUG=false
export KLONE_DATA_DIR="${KLONE_DATA_DIR:-$HOME/.local/share/klone}"
export KLONE_DB_PATH="${KLONE_DB_PATH:-$KLONE_DATA_DIR/klone_mission_control.db}"
umask 077
mkdir -p "$KLONE_DATA_DIR"
chmod 700 "$KLONE_DATA_DIR"

python tools/local_deploy.py doctor
if [ ! -x .venv/bin/python ]; then
  python tools/local_deploy.py install
fi
exec python tools/local_deploy.py start "$@"
