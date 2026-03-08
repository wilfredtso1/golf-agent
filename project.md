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

## Update Protocol
After each completed implementation step, update this file:
1. Add one line under **Current State (Latest)** with what changed.
2. If architecture changed, update **Architecture** bullets.
3. If goals changed, update **Goals**.

## Last Updated
- 2026-03-08: Added deployment runbook, CI workflow, env-contract test coverage, validated Railway US-East production deployment, added persistent courses catalog, wired shared course suggestions into form flows, and added persistent course upserts from form + lead-trigger interactions.
