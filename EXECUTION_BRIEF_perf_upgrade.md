# Performance Upgrade Execution Brief

Date: 2026-03-08
Owner: Execution agent
Scope: Backend performance, reliability, and production hardening for `golf-agent`.

## Goal
Improve throughput and operational safety without changing core product behavior (lead trigger, form response, SMS routing, proposal and confirm flows).

## Constraints
- Use smallest safe changes per slice.
- One slice per PR/change set.
- Do not mix unrelated refactors.
- Keep `outstanding_product_decisions.md` untouched.

## Slice Plan (in order)

### Slice 1: Remove runtime DDL from hot paths
Behavior change: remove `CREATE TABLE IF NOT EXISTS` from request-time code paths (`list_courses`, `upsert_course_snapshot`).

Tasks:
- Remove `ensure_courses_table()` usage from hot-path functions.
- Keep schema ownership in `schema.sql`/migration flow only.
- Ensure failure mode is explicit (DB error if schema missing).

Acceptance criteria:
- No runtime `CREATE TABLE` statements in `tools.py` hot-path functions.
- Existing tests pass.
- Local smoke endpoints still import and run.

Required checks:
- `python3 -m pytest -q`

Rollback:
- Reintroduce guarded `ensure_courses_table` calls if environment cannot guarantee schema application.

### Slice 2: Validate form payload enums and course integrity
Behavior change: reject invalid `available_time_blocks` and non-session `approved_courses` in `/api/form-response`.

Tasks:
- Add strict validation for allowed time-block enums.
- Validate approved courses are in session candidate courses.
- Add tests for invalid and mixed payloads.

Acceptance criteria:
- Invalid payloads return `400` with actionable detail.
- Valid payloads unchanged.

Required checks:
- `python3 -m pytest -q`
- Targeted tests for form-response validation

Rollback:
- Feature-flag strict validation if needed.

### Slice 3: Decouple SMS provider calls from DB transaction windows
Behavior change: avoid network send operations while DB transaction is open for core webhook and invite sends.

Tasks:
- Add outbound message queue/outbox table or post-commit send pattern.
- Preserve inbound SID dedupe semantics.
- Add retry-safe send handling.

Acceptance criteria:
- No provider network call inside main DB transaction path.
- Duplicate inbound SID remains idempotent.

Required checks:
- `python3 -m pytest -q`
- `RUN_DB_INTEGRATION_TESTS=1 python3 -m pytest -q tests/test_integration_flow.py`

Rollback:
- Revert to in-transaction send path.

### Slice 4: Webhook concurrency safety
Behavior change: prevent event-loop blocking in `/webhooks/twilio/sms`.

Tasks:
- Switch endpoint to sync or run blocking work in threadpool.
- Keep Twilio signature and response semantics unchanged.

Acceptance criteria:
- No blocking sync workload directly in async event-loop context.
- Regression tests pass.

Required checks:
- `python3 -m pytest -q`
- Local webhook smoke via `/dev/simulate-sms`

Rollback:
- Revert endpoint signature/dispatch strategy.

### Slice 5: DB connection pooling and query hygiene
Behavior change: reduce connection churn and improve concurrency.

Tasks:
- Introduce connection pool lifecycle.
- Update `get_conn()` to use pool.
- Review indexes for frequently accessed filters.

Acceptance criteria:
- No per-request full connect churn for hot endpoints.
- Tests and smoke checks pass.

Required checks:
- `python3 -m pytest -q`
- Optional concurrency sanity script

Rollback:
- Revert to direct connection management.

### Slice 6: Observability and reliability hardening
Behavior change: eliminate silent provider failures and improve diagnostics.

Tasks:
- Add explicit logging in reminder SMS failures.
- Standardize structured log fields for key transitions/errors.
- Update docs for runtime behavior and operations.

Acceptance criteria:
- No silent `except` in reminder sends.
- `project.md`, `todo.md`, `SPEC.md` are aligned.

Required checks:
- `python3 -m pytest -q`

Rollback:
- Revert logging behavior if noisy.

## Definition Of Done Per Slice
- Slice acceptance criteria met.
- Required checks executed with outcomes recorded.
- `project.md` updated with a dated state delta.
- `todo.md` updated with next actionable items.
- Residual risks documented.
