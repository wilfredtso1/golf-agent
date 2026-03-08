# Golf Agent Backend

Agent to coordinate and book group tee times.

## Local backend checks

1. Install dependencies:

```bash
pip3 install -r requirements.txt
```

2. Ensure `.env` is configured.

3. Start API:

```bash
python3 -m uvicorn main:app --host 127.0.0.1 --port 8010
```

4. Run Supabase smoke test:

```bash
python3 dev_smoke_backend.py
```

## Twilio blocked workaround (number auth pending)

Set these env vars in `.env` for local-only development:

```dotenv
TWILIO_VALIDATE_SIGNATURE=false
SMS_SEND_ENABLED=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Then simulate inbound SMS without Twilio:

```bash
python3 dev_simulate_sms.py --from-number "+19175550123" --body "late morning works, bethpage"
```

This hits `POST /dev/simulate-sms` and exercises the same backend processing as the Twilio webhook.

### Optional: inspect session status/proposals

```bash
curl -sS "http://127.0.0.1:8010/api/session-status?session_id=<SESSION_UUID>"
```

## API Examples

### `POST /api/lead-trigger`

```bash
curl -sS -X POST http://127.0.0.1:8010/api/lead-trigger \
  -H 'Content-Type: application/json' \
  -d '{
    "lead_phone":"+19175550100",
    "lead_name":"Will",
    "target_date":"2026-03-15",
    "candidate_courses":["Maple Moor","Silver Lake"],
    "invitees":[{"name":"Dave","phone":"+19175550123"}],
    "send_invites":false
  }'
```

### `GET /api/session-status`

```bash
curl -sS "http://127.0.0.1:8010/api/session-status?session_id=<SESSION_UUID>"
```

### `POST /api/form-response`

Get a signed token first:

```bash
python3 dev_generate_form_link.py --base-url http://127.0.0.1:5173/golf-form
```

Take `token=...` from output, then submit:

```bash
curl -sS -X POST http://127.0.0.1:8010/api/form-response \
  -H 'Content-Type: application/json' \
  -d '{
    "token":"<TOKEN>",
    "is_attending":true,
    "approved_courses":["Maple Moor"],
    "available_time_blocks":["late_morning"]
  }'
```

### Course catalog

Seed canonical courses:

```bash
python3 dev_seed_courses.py
```

Inspect persistent course snapshots:

```bash
curl -sS http://127.0.0.1:8010/api/courses
```

### Reminder/escalation job (cron target)

```bash
curl -sS -X POST http://127.0.0.1:8010/jobs/reminders
```

Behavior:
- >= 4 hours since invite with no response: reminder sent to player
- >= 8 hours since invite with no response: escalation sent to lead, player marked `unresponsive`

### Lead confirmation gate flow

After proposals are generated, lead must explicitly confirm:

```text
1
CONFIRM 1
```

The first message stages the pick; `CONFIRM <n>` executes the commitment.

Session-management commands from the lead execute immediately (no extra confirmation):
- `add <name> <phone>`
- `remove <name>`
- `change date to YYYY-MM-DD`
- `change courses: <course1>, <course2>, ...`

## Tests

```bash
pytest -q
```

Run DB-backed integration tests (includes proposal + confirm lifecycle):

```bash
RUN_DB_INTEGRATION_TESTS=1 python3 -m pytest -q tests/test_integration_flow.py
```

## One-command demo flow

Run a full demo script (trigger -> player reply -> proposal -> lead confirm):

```bash
python3 dev_demo_flow.py --base-url http://127.0.0.1:8010
```

Against Railway:

```bash
python3 dev_demo_flow.py --base-url https://golf-agent-production.up.railway.app
```

Quick guided runbook (health + flow + course snapshot):

```bash
./scripts/run_demo_5min.sh
```

See [DEMO.md](DEMO.md) for the full 5-minute walkthrough.

Machine-readable demo readiness report:

```bash
python3 scripts/demo_report.py --base-url http://127.0.0.1:8010 --pretty
```

Default seeded demo courses:
`Maple Moor, Silver Lake, La Tourette, Dyker, Pelham, Saxon Woods, Forest Hills`


Search shared courses:

```bash
curl -sS "http://127.0.0.1:8010/api/courses?q=maple&limit=10"
```
