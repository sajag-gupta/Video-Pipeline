#!/usr/bin/env bash
# One-command workspace setup for macOS / Linux.
#   ./setup.sh                 full setup
#   ./setup.sh --no-node       skip Node/HyperFrames
#   ./setup.sh --skills        also install HyperFrames agent skills
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print("%d%02d"%sys.version_info[:2])')
    if [ "$v" -ge 311 ] && [ "$v" -lt 314 ]; then PY="$c"; break; fi
  fi
done
if [ -z "$PY" ]; then echo "Python 3.11-3.13 required (https://www.python.org/downloads/)"; exit 1; fi
echo "Using Python: $(command -v "$PY")"

[ -x venv/bin/python ] || "$PY" -m venv venv
venv/bin/python -m pip install --upgrade pip --quiet
echo "Installing Python packages (first run takes a few minutes)..."
venv/bin/python -m pip install -r requirements.txt --quiet
venv/bin/python scripts/setup_workspace.py "$@"
echo
echo "Done. Next: venv/bin/python vp.py help"
