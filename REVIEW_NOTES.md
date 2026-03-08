# Code Review Notes

**Reviewer:** Staff engineer cleanup pass
**Date:** 2026-03-08
**Scope:** Correctness, safety, dead-code removal, error handling, prompt hygiene, DRY

---

## (a) Highest-Severity Issues — Found and Fixed

### 1. Silent failure path on agent exceptions → Twilio retry loop
**File:** `main.py` — `_process_inbound_sms`
**Severity:** HIGH

`process_inbound_message()` was called without any error handling. If it threw an unexpected exception, FastAPI returned a 500 to Twilio. Twilio would then retry the webhook, but the inbound deduplication guard (`ON CONFLICT DO NOTHING` on `provider_message_sid`) would silently swallow the retry — the player never gets a reply and no one notices.

**Fix:** Wrapped the agent dispatch in `try/except`, logging the exception internally and returning a safe generic reply so Twilio always gets a 200.

---

### 2. Phone number logged in plaintext
**File:** `main.py:277`
**Severity:** MEDIUM

`logger.exception("Failed to send invite SMS to %s", target["phone"])` wrote a full E.164 phone number to the log stream, which is stored long-term on Railway.

**Fix:** Masked to last 4 digits only: `"Failed to send invite SMS to ***%s", str(target["phone"])[-4:]`

---

### 3. `_insert_outbound_message` duplicated across two files
**Files:** `main.py`, `reminders.py`
**Severity:** MEDIUM

The exact same 10-line DB function existed independently in both files. Any schema or behaviour change had to be made in two places, with no guarantee they'd stay in sync.

**Fix:** Moved the canonical implementation to `tools.py` as `insert_outbound_message` (public, keyword-only args). Both callers now import and use it.

---

### 4. `_build_form_url` duplicated across two files
**Files:** `main.py`, `agent.py`
**Severity:** LOW-MEDIUM

Identical one-liner URL builder existed in both modules. If `FORM_BASE_URL` handling ever changed, one copy would likely be missed.

**Fix:** Moved to `token_utils.py` as `build_form_url` (public). Both callers import from there. `urlencode` import removed from both `main.py` and `agent.py`.

---

### 5. `_ensure_proposals` was a pointless one-liner wrapper
**File:** `agent.py`
**Severity:** LOW

```python
def _ensure_proposals(cur, session, policy):
    return ensure_session_proposals(cur, session, policy)
```

Added zero semantics. Its only effect was making monkeypatching in tests target the wrong symbol.

**Fix:** Deleted. Both call sites now call `ensure_session_proposals` directly. The test's `monkeypatch.setattr` target updated to match.

---

### 6. `get_active_confirmed_player_ids` was dead code
**File:** `tools.py`
**Severity:** LOW

Defined but never imported or called anywhere in the codebase.

**Fix:** Deleted.

---

### 7. LLM call had no `max_tokens` set
**File:** `llm.py`
**Severity:** LOW-MEDIUM

The OpenAI payload had `temperature: 0` but no `max_tokens`. If the model produced a runaway response, the JSON would be malformed (truncated mid-token) and silently return `None` from the JSON parse. More critically, no explicit limit means billing exposure and unpredictable latency.

**Fix:** Added `max_tokens: 256` (a generous ceiling for the expected JSON structure). Added as a named constant `_INTENT_MAX_TOKENS` with a comment explaining the intent.

---

### 8. LLM system prompt was an anonymous inline string
**File:** `llm.py`
**Severity:** LOW

The prompt string was buried inside `parse_intent_with_llm()`, making it non-auditable without reading implementation code.

**Fix:** Extracted to module-level constant `_INTENT_SYSTEM_PROMPT`. Prompt changes are now visible in a single, findable place.

---

## (b) Issues Flagged but Not Fixed (require product decisions)

### B1. `ensure_courses_table` runs DDL on every query
**Files:** `tools.py` — `upsert_course_snapshot`, `list_courses`
**Why not fixed:** Removing it requires confirming the schema migration script is always run before deploy. The `CREATE TABLE IF NOT EXISTS` is safe but acquires a schema lock on every call. In production under load, this will cause contention. The right fix is to remove the `ensure_courses_table()` calls and rely solely on the `schema.sql` migration — but that requires deployment coordination.

### B2. `async def twilio_sms_webhook` blocks the event loop
**File:** `main.py`
**Why not fixed:** The endpoint is `async def` (required because `await request.form()` is async), but the entire DB processing path underneath is synchronous psycopg, which blocks the event loop thread. Under concurrent load this will serialize all Twilio webhooks. The correct fix is either switching to `psycopg-async` or wrapping `_process_inbound_sms` in `asyncio.run_in_executor`. This is an architectural change that affects DB connection pooling.

### B3. No TTL / cleanup for abandoned sessions
**File:** `tools.py`, `reminders.py`
**Why not fixed:** Sessions in `collecting` status that never complete accumulate forever. There is no scheduled cleanup. Fixing this requires deciding the business rule: how long should a session stay open? What happens to it when it expires? Product decision required.

### B4. `_generate_session_code` has a TOCTOU race
**File:** `main.py`
**Why not fixed:** The code checks if a session code is in use and then inserts it, without holding a lock between those two operations. Under concurrent `lead_trigger` calls, two sessions could get the same code. The fix is either a unique constraint + retry loop, or generating codes from a sequence. The current code has a 40-retry loop which reduces (but does not eliminate) the risk. Severity is low at current traffic but worth hardening before high volume.

### B5. `invite_results` exposes `str(exc)` to API callers
**File:** `main.py:279`
**Why not fixed:** When an SMS send fails, the raw exception message is returned in the `lead_trigger` API response as `"error": str(exc)`. For an internal admin API this is acceptable, but if this endpoint is ever exposed publicly it leaks Twilio error internals. Flag for review when access control is defined.

### B6. No inbound SMS message length validation
**File:** `main.py` — `_process_inbound_sms`
**Why not fixed:** No explicit check on `Body` length. Twilio caps SMS at 1600 characters but concatenated messages can be longer. Add `if len(body) > 2000: ...` guard once the intended limit is decided.

---

## (c) Testing Gaps

The following core-logic functions have no direct unit tests. Tests should be added before changing these functions.

| Function | File | What a minimal test would assert |
|---|---|---|
| `_parse_time_blocks` | `agent.py` | Given `"late morning works"`, returns `["late_morning"]`; given empty string, returns `[]` |
| `_parse_courses` | `agent.py` | Exact name match returns the course; partial non-match returns nothing |
| `_extract_option_number` | `agent.py` | `"option 2 please"` → `2`; `"no number here"` → `None` |
| `_format_policy_summary` | `agent.py` | Conflict path returns the conflict message; overlap path names courses and times |
| `_format_proposals_message` | `agent.py` | Empty list returns the not-found string; populated list includes course and price |
| `normalize_phone` | `twilio_helpers.py` | 10-digit US number gets `+1` prefix; 11-digit with leading 1 strips it; garbage raises `InvalidPhoneNumber` |
| `generate_form_token` / `verify_form_token` | `token_utils.py` | Round-trip succeeds; expired token raises; tampered signature raises |
| `replace_tee_time_proposals` | `tools.py` | Existing proposals are deleted before new ones are inserted (idempotency) |
| `_generate_session_code` | `main.py` | Returns a 4-digit zero-padded string; never returns a code already in use |
| `ensure_session_proposals` | `tools.py` | Returns `[]` when policy has no overlap; returns proposals and transitions session to `proposing` when overlap exists |

**Missing edge cases in existing tests:**
- `test_agent.py`: No test for lead sending `CONFIRM <n>` where `n` is out of range.
- `test_agent.py`: No test for LLM returning malformed / unexpected JSON (the `_maybe_parse_intent_with_llm` path returning `None`).
- `test_lead_actions.py`: No test for `PROCEED WITHOUT THEM` when minimum group size is not met.
- `test_reminders.py`: No test for the escalation path actually marking the player as `unresponsive`.
- No tests cover the case where all players decline (empty confirmed set in `evaluate_session`).
- No tests cover the ambiguous-session reply path (`_format_ambiguous_session_reply`).
