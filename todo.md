# Golf Agent TODO

## In Progress
- [ ] Validate lead-action confirmation flows against live Supabase data path (add/remove/date/courses).

## Next Up
- [ ] Add DB-backed integration test for lead action staging + `CONFIRM ACTION` execution.
- [ ] Implement explicit handling for `PROCEED WITHOUT THEM` after 8h escalation.
- [ ] Add structured logging for all session state transitions.
- [ ] Add openapi docs/examples for `/api/lead-trigger`, `/api/form-response`, `/api/session-status`.

## Twilio Go-Live
- [ ] Verify authenticated Twilio number can receive/send production SMS.
- [ ] Set `TWILIO_VALIDATE_SIGNATURE=true` in deployed env.
- [ ] Set `SMS_SEND_ENABLED=true` in deployed env.
- [ ] Run real-phone end-to-end test from trigger -> confirm.

## GolfNow Integration
- [ ] Build `golfnow_adapter.py` implementing the same shape as `search_tee_times`.
- [ ] Add provider failure/retry behavior and fallback messaging.
- [ ] Add feature flag to switch between mock and GolfNow provider.

## Handoff Notes
- Core deterministic flow is functional locally and in DB-backed smoke tests.
- Use `project.md` for architecture/current-state context before resuming work.
- Run `python3 -m pytest -q` first; run DB integration tests when needed.
