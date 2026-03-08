# Deployment Runbook

## Git/GitHub

```bash
cd /Users/wilfredtso/golf-agent
git status
git add .
git commit -m "<message>"
git push origin main
```

If push is rejected due to remote history:

```bash
git fetch origin
git pull --no-rebase origin main --allow-unrelated-histories
# resolve conflicts if any
git add .
git commit -m "Merge remote main"
git push origin main
```

## Railway Setup

### Link project/service

```bash
railway project link -p golf-agent
railway service link golf-agent
railway status
```

### Required production variables

- `DATABASE_URL` (Supabase pooler URI)
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `FORM_TOKEN_SECRET`

### Recommended production variables

- `TWILIO_ACCOUNT_SID`
- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-4o-mini`
- `TWILIO_VALIDATE_SIGNATURE=true`
- `SMS_SEND_ENABLED=false` (until Twilio is ready)
- `CORS_ALLOW_ORIGINS=<frontend-origins>`
- `FORM_BASE_URL=<your-form-url>`
- `FORM_TOKEN_TTL_SECONDS=604800`
- `DEFAULT_TIMEZONE=America/New_York`

### Set variables via CLI

```bash
railway variable set KEY=value -e production -s golf-agent
```

### Redeploy and check

```bash
railway redeploy --yes
railway service status
railway logs --tail 120
```

## Post-deploy smoke checks

```bash
curl -sS https://golf-agent-production.up.railway.app/health
```

```bash
curl -sS -X POST https://golf-agent-production.up.railway.app/dev/simulate-sms \
  -H 'Content-Type: application/json' \
  -d '{"from_number":"+19175550123","body":"late morning works, bethpage"}'
```

Expected:
- `/health` returns `{"status":"ok"}`
- `/dev/simulate-sms` returns `{"ok":true,...}`

## Region management

Move service to US East:

```bash
railway scale --service golf-agent --environment production --us-east4-eqdc4a 1 --europe-west4-drams3a 0
```

## Common failures

- `Missing required environment variable: DATABASE_URL`
  - Set `DATABASE_URL` in Railway variables.
- `password authentication failed for user ...`
  - Use exact Supabase pooler URI and URL-encode password.
- `Network is unreachable` to `db.<project>.supabase.co`
  - Use Supabase **pooler** URI, not direct DB host.

## Production schema + seed

Apply latest schema to production DB:

```bash
cd /Users/wilfredtso/golf-agent
railway run python3 - <<'PY'
from pathlib import Path
import os
import psycopg

sql = Path('schema.sql').read_text()
with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
print('SCHEMA_APPLIED')
PY
```

Seed shared courses in production:

```bash
cd /Users/wilfredtso/golf-agent
railway run python3 dev_seed_courses.py
```
