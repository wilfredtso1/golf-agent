#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-golf-agent}"
ENVIRONMENT="${2:-production}"

if [[ ! -f "schema.sql" ]]; then
  echo "Run this script from the repo root (schema.sql not found)." >&2
  exit 1
fi

railway run --service "${SERVICE}" --environment "${ENVIRONMENT}" python3 - <<'PY'
from pathlib import Path
import psycopg

sql = Path("schema.sql").read_text()
with psycopg.connect() as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
print("SCHEMA_APPLIED")
PY
