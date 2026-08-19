#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT_DIR/.venv-wsl311/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: reviewer environment is missing; run bash scripts/reviewer_setup.sh first." >&2
  exit 1
fi

cd "$ROOT_DIR"
echo "Dashboard: http://localhost:8765/ (Ctrl+C to stop)"
exec "$PYTHON" dashboard/interactive_server.py --port 8765
