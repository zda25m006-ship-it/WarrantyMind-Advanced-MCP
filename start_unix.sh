#!/usr/bin/env bash
set -e
echo "=== WarrantyMind Local Warranty Workflow ==="
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
./.venv/bin/pip install -r requirements.txt
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
echo "Starting WarrantyMind AI on http://127.0.0.1:8000 ..."
./.venv/bin/python -m uvicorn warrantymind.main:app --host 127.0.0.1 --port 8000
