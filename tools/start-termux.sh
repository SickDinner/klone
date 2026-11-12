#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python tools/local_deploy.py doctor
if [ ! -x .venv/bin/python ]; then
  python tools/local_deploy.py install
fi
exec python tools/local_deploy.py start "$@"
