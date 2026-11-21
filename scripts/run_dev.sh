#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d node_modules ]]; then
  npm install
fi
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m playwright install chromium

printf 'Start the local backend in a second terminal with:\n  .venv/bin/python backend/run_backend.py\n'
printf 'Then start the UI with:\n  npm run dev\n'
