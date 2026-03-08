#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8010}"

echo "[1/3] Health check: ${BASE_URL}/health"
curl -fsS "${BASE_URL}/health" >/dev/null
echo "health ok"

echo "[2/3] Running full simulated coordination flow"
python3 dev_demo_flow.py --base-url "${BASE_URL}"

echo "[3/3] Fetching seeded/shared courses sample"
curl -fsS "${BASE_URL}/api/courses?limit=5"
echo
echo "demo complete"
