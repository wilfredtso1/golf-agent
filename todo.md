# Golf Agent TODO

## In Progress
- [x] Validate lead-action confirmation flows against live Supabase data path (add/remove/date/courses).
- [x] Update local `DATABASE_URL` to Supabase pooler host and re-run DB-backed integration tests.

## Next Up
- [x] Dry-run the 5-minute demo runbook against Railway and capture expected output snippets in `DEMO.md`.
- [x] Add DB-backed integration test for lead action staging + `CONFIRM ACTION` execution.
- [x] Implement explicit handling for `PROCEED WITHOUT THEM` after 8h escalation.
- [x] Add structured logging for all session state transitions.
- [x] Add openapi docs/examples for `/api/lead-trigger`, `/api/form-response`, `/api/session-status`.
- [x] Add machine-readable demo report script for fast go/no-go checks.
- [ ] Remove or repurpose unused `pending_confirmations` flow now that lead session actions are immediate.
- [ ] Add CI target (manual workflow or nightly) for DB-backed eval scenarios (`tests/test_eval_scenarios.py`).

## DevOps / Quality
- [x] Add repo-level `AGENTS.md` guidance and reusable production shipping skill for future agents.
- [x] Automate production schema migration step (scripted via `scripts/apply_schema_railway.sh`).
- [x] Create deployment runbook (`DEPLOYMENT.md`).
- [x] Add GitHub Actions CI to run tests on push/PR.
- [x] Add env-example contract test to prevent missing required variables.
- [x] Validate Railway production deployment in US East with live smoke checks.
- [x] Add CI job for DB-backed integration tests behind secrets/environment.

## Twilio Go-Live
- [ ] Verify authenticated Twilio number can receive/send production SMS.
- [x] Set `TWILIO_VALIDATE_SIGNATURE=true` in deployed env.
- [ ] Set `SMS_SEND_ENABLED=true` in deployed env.
- [ ] Run real-phone end-to-end test from trigger -> confirm.

## Data / Catalog
- [x] Add persistent `courses` table and keep snapshots updated from proposals.
- [x] Apply latest DB schema in production and seed shared courses catalog.
- [x] Add course metadata enrichment (location, tee-sheet provider id, borough/region tags).

## GolfNow Integration
- [x] Build semantic course retrieval over shared catalog for GolfNow matching.
- [x] Build `golfnow_adapter.py` scaffold implementing the same shape as `search_tee_times`.
- [x] Add provider failure/retry behavior and fallback messaging.
- [x] Add feature flag to switch between mock and GolfNow provider.

## Handoff Notes
- Core deterministic flow is functional locally and in DB-backed smoke tests.
- Railway production deploy is live with successful `/health` and `/dev/simulate-sms` checks.
- Use `project.md` for architecture/current-state context before resuming work.
- Run `python3 -m pytest -q` first; run DB integration tests when needed.
