# 5-Minute Demo Runbook

This runbook demonstrates the core coordination flow without Twilio dependency.

## Local Demo
1. Start backend in one terminal:
```bash
python3 -m uvicorn main:app --host 127.0.0.1 --port 8010
```

2. In a second terminal, run:
```bash
./scripts/run_demo_5min.sh
```

Expected result:
- Health check passes.
- `DEMO_FLOW_OK` prints.
- Output includes a new `session_id`, `final_session_status`, and proposal count.

## Railway Demo
Run the same flow against production:
```bash
./scripts/run_demo_5min.sh https://golf-agent-production.up.railway.app
```

Expected result:
- Health check passes on Railway.
- `DEMO_FLOW_OK` prints for a full simulated round.

### Verified Output Snapshot (2026-03-08)
From:
```bash
./scripts/run_demo_5min.sh https://golf-agent-production.up.railway.app
```

Observed:
- `health ok`
- `DEMO_FLOW_OK`
- `mid_session_status=proposing`
- `final_session_status=confirmed`
- booking handoff reply returned:
  - `Confirmed option 1. Book here for the group: https://booking.mock.golf/checkout?...`

## Optional Form UX Proof
Generate a signed form URL:
```bash
python3 dev_generate_form_link.py --base-url http://127.0.0.1:5173/golf-form
```

Open the `form_url` output in browser and submit once.
