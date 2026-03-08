# Golf Agent Project

## Goals
- Build an AI-assisted SMS coordination agent for golf tee times.
- Enforce deterministic policy and lead confirmation gates in code.
- Collect structured player preferences through forms and keep conversational updates via SMS.
- Propose tee times and hand booking to the lead.

## Architecture
- Backend: FastAPI webhook + API endpoints.
- Data: Postgres/Supabase (`players`, `sessions`, `session_players`, `messages`, `tee_time_proposals`, `courses`).
- Messaging: Twilio SMS (with local `/dev/simulate-sms` fallback).
- Agent runtime:
  - Context assembly from DB
  - Rule-first execution with optional LLM intent extraction
  - Deterministic policy checks and action gates
- Tee-time search: mock provider now (`mock_booking_api.py`), replaceable with GolfNow adapter.
- Background jobs: reminder/escalation endpoint (`/jobs/reminders`) suitable for cron.
- Deployment operations: Railway runbook + region management + smoke-check procedure in `DEPLOYMENT.md`.

## Current State (Latest)
- Working lead trigger + form response ingestion + session/player/message persistence.
- Working inbound SMS flow with dev simulation and Twilio-signature toggle.
- Working proposal lifecycle:
  - overlap detection
  - proposal generation
  - lead pick staging
  - `CONFIRM <n>` booking handoff gate
- Working reminder/escalation engine (4h reminder, 8h escalation).
- Added durable lead-action gate with `pending_confirmations` table support:
  - add player
  - remove player
  - change date
  - change courses
  - all executed only after `CONFIRM ACTION <token>`.
- GitHub + Railway deployment path now operational; production smoke checks pass.
- Added persistent `courses` catalog updated from proposal generation (latest price + booking URL snapshots).
- Railway production service is running in US East (`us-east4-eqdc4a`) with `/health` and `/dev/simulate-sms` returning 200.
- Course catalog endpoint now supports query filtering and form context now includes shared course suggestions.
- Form flow now reads shared course suggestions and can add new course names into the shared catalog.
- Applied latest schema to production DB and seeded the shared courses catalog (7 courses).
- Added reusable `golf-agent-production-shipping` skill plus repo `AGENTS.md` so future agents consistently run tests, deploy checks, and continuity doc updates.
- Added reusable prompt templates and a 5-minute demo runbook/script (`PROMPTS.md`, `DEMO.md`, `scripts/run_demo_5min.sh`) for fast walkthroughs.
- Verified the 5-minute demo runbook against Railway production with `DEMO_FLOW_OK` and confirmed session transition to `confirmed`.
- Added DB-backed integration coverage for lead-action staging and `CONFIRM ACTION` add-player execution flow.
- Added explicit lead command handling for `PROCEED WITHOUT THEM` to continue proposal generation after unresponsive escalations.
- Added structured logs for session/player status transitions in `tools.py` to improve production traceability.
- Added concrete API example docs for lead trigger, session status, and form response flows in `README.md`.
- Added automated Railway schema-apply script (`scripts/apply_schema_railway.sh`) and wired it into deployment docs.
- Added CI DB-integration job gated by `secrets.DATABASE_URL` to continuously validate live DB flows.
- Expanded DB-backed integration coverage to include staged/confirmed lead date-change actions.
- Expanded DB-backed integration coverage to include all staged/confirmed lead actions (add/remove/date/courses).
- Enriched seeded shared courses with metadata tags (region/provider) and merged metadata support in course upserts.
- Added tee-time provider abstraction (`TEE_TIME_PROVIDER`) with `golfnow_adapter.py` scaffold and mock/GolfNow switch path.

## Update Protocol
After each completed implementation step, update this file:
1. Add one line under **Current State (Latest)** with what changed.
2. If architecture changed, update **Architecture** bullets.
3. If goals changed, update **Goals**.

## Last Updated
- 2026-03-08: Added deployment runbook, CI workflow, env-contract test coverage, validated Railway US-East production deployment, added persistent courses catalog, wired shared course suggestions into form flows, added persistent course upserts from form + lead-trigger interactions, and validated production DB schema/seed operations via Railway runtime.
- 2026-03-08: Added reusable production-shipping skill (`~/.codex/skills/golf-agent-production-shipping`) and repo-level `AGENTS.md` enforcement for consistent staff-level execution/handoff practices.
- 2026-03-08: Added reusable Codex prompt templates and a deterministic 5-minute demo runbook/script for local or Railway walkthroughs.
- 2026-03-08: Executed the 5-minute runbook against Railway production and documented expected output snapshot in `DEMO.md`.
- 2026-03-08: Added integration test for lead-action staging + `CONFIRM ACTION` execution (local execution requires reachable pooler `DATABASE_URL`).
- 2026-03-08: Implemented and unit-tested `PROCEED WITHOUT THEM` lead command behavior for escalation follow-through.
- 2026-03-08: Added state-transition logging for session and player status changes across core write paths.
- 2026-03-08: Added runnable API examples for `/api/lead-trigger`, `/api/session-status`, and `/api/form-response`.
- 2026-03-08: Automated production schema migration command via script and updated `DEPLOYMENT.md`.
- 2026-03-08: Added GitHub Actions DB integration workflow (secret-gated) for `tests/test_integration_flow.py`.
- 2026-03-08: Verified local pooler `DATABASE_URL` and expanded DB integration tests (`add_player` + `change_date` confirm-action flows).
- 2026-03-08: Completed DB-backed confirm-action integration coverage for `add`, `remove`, `change date`, and `change courses`.
- 2026-03-08: Added course metadata enrichment in seed data and snapshot merge path for shared catalog quality.
- 2026-03-08: Added provider feature flag and GolfNow adapter scaffold while preserving mock provider as default.
