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

## Optional Form UX Proof
Generate a signed form URL:
```bash
python3 dev_generate_form_link.py --base-url http://127.0.0.1:5173/golf-form
```

Open the `form_url` output in browser and submit once.
