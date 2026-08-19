#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-wsl311"

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker is required in WSL." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "ERROR: Docker daemon is not reachable from WSL." >&2; exit 1; }

cd "$ROOT_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt
docker build -f Dockerfile.iperf -t my-iperf-tc .
"$VENV_DIR/bin/python" -m unittest discover -s tests -v

echo "Reviewer setup complete. No formal experiment matrix was run."
echo "Start the Dashboard with: bash scripts/reviewer_dashboard.sh"
