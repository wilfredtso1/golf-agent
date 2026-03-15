# Golf Agent TODO

## In Progress
- [x] Validate lead-action confirmation flows against live Supabase data path (add/remove/date/courses).
- [x] Update local `DATABASE_URL` to Supabase pooler host and re-run DB-backed integration tests.

## Next Up
- [x] Dry-run the 5-minute demo runbook against Railway and capture expected output snippets in `DEMO.md`.
- [x] Add DB-backed integration tests for lead session-management actions under immediate execution.
- [x] Implement explicit handling for `PROCEED WITHOUT THEM` after 8h escalation.
- [x] Add structured logging for all session state transitions.
- [x] Add openapi docs/examples for `/api/lead-trigger`, `/api/form-response`, `/api/session-status`.
- [x] Add machine-readable demo report script for fast go/no-go checks.
- [x] Remove unused `pending_confirmations` runtime flow now that lead session actions are immediate.
- [ ] Add CI target (manual workflow or nightly) for DB-backed eval scenarios (`tests/test_eval_scenarios.py`).
- [x] Slice 6: observability/reliability hardening — standardized structured log fields, upgraded GolfNow error logging from warning to exception (preserves stack trace), aligned log message format across main.py.
- [x] Add short session-code routing for ambiguous multi-session inbound SMS from the same phone number.
- [x] Deduplicate proposal-generation flow so agent and form-response paths share one policy/search/proposal helper.
- [x] Improve ambiguous multi-session routing with code-only disambiguation and recent-session hint reuse.

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

## Code Quality (from review pass)
- [ ] Add unit tests for `_parse_time_blocks`, `_parse_courses`, `_extract_option_number` (see `REVIEW_NOTES.md` section c)
- [ ] Add unit tests for `normalize_phone` edge cases
- [ ] Add unit tests for `generate_form_token` / `verify_form_token` round-trip + expiry
- [x] Remove `ensure_courses_table` DDL-on-every-call once schema migration is confirmed reliable (see `REVIEW_NOTES.md` section b)
- [x] Enforce strict `/api/form-response` validation for time-block enums and session-candidate course integrity.
- [x] Decouple outbound SMS sends from core DB transaction windows in lead-trigger/webhook/form-response paths.
- [x] Fix `async def twilio_sms_webhook` to not block the event loop (via FastAPI threadpool dispatch).
- [x] Improve query hygiene and add supporting indexes for active-session/message-history lookups.
- [x] Harden active `session_code` uniqueness with DB constraint + retry logic to remove concurrent create race.
- [x] Apply schema in production and verify `uq_sessions_active_session_code` exists.
- [x] Fix Railway schema apply script to connect using `DATABASE_URL` explicitly.

## Handoff Notes
- Core deterministic flow is functional locally and in DB-backed smoke tests.
- Railway production deploy is live with successful `/health` and `/dev/simulate-sms` checks.
- Use `project.md` for architecture/current-state context before resuming work.
- Run `python3 -m pytest -q` first; run DB integration tests when needed.
- Execution brief active: `EXECUTION_BRIEF_perf_upgrade.md`.
- Next managed slice: Slice 6 (observability/reliability hardening; then reassess whether dedicated pooling dependency is still needed).
