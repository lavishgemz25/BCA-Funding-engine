#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# One-click local run (macOS/Linux)
# Requires: python3.11+

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "Creating .env..."
  python tools/gen_env.py
fi

echo "Starting server on http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
