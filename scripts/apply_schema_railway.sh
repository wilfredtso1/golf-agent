#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-golf-agent}"
ENVIRONMENT="${2:-production}"

if [[ ! -f "schema.sql" ]]; then
  echo "Run this script from the repo root (schema.sql not found)." >&2
  exit 1
fi

railway run --service "${SERVICE}" --environment "${ENVIRONMENT}" python3 - <<'PY'
import os
from pathlib import Path
import psycopg

sql = Path("schema.sql").read_text()
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL is not set in Railway service environment")

with psycopg.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
print("SCHEMA_APPLIED")
PY
