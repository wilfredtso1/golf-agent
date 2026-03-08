"""Eval harness: 15 realistic scenarios covering core agent behavior.

Each test checks both reply text and resulting DB state, so a regression
in either surface area will fail loudly.

Run with:
    RUN_DB_INTEGRATION_TESTS=1 pytest tests/test_eval_scenarios.py -v
"""
from __future__ import annotations

import os
import random
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb

from db import get_conn
from main import LeadInvitee, LeadTriggerPayload, _process_inbound_sms, lead_trigger, session_status
from reminders import run_reminder_cycle

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION_TESTS", "0") != "1",
    reason="Set RUN_DB_INTEGRATION_TESTS=1 to run DB-backed integration tests.",
)

_TARGET_DATE = date.today() + timedelta(days=7)


# ── shared helpers ────────────────────────────────────────────────────────────

def _phone(area: str = "917") -> str:
    return f"+1{area}{random.randint(1000000, 9999999)}"


def _sid() -> str:
    return f"eval-{uuid4().hex}"


def _sms(phone: str, body: str) -> str:
    return _process_inbound_sms({"From": phone, "Body": body, "MessageSid": _sid()})


def _trigger(
    lead_phone: str,
    invitees: list[tuple[str, str]],
    courses: list[str] | None = None,
) -> dict:
    return lead_trigger(
        LeadTriggerPayload(
            lead_phone=lead_phone,
            lead_name="Eval Lead",
            target_date=_TARGET_DATE,
            candidate_courses=courses or ["Bethpage", "Marine Park"],
            invitees=[LeadInvitee(name=n, phone=p) for n, p in invitees],
            send_invites=False,
        )
    )


def _session_info(session_id: str) -> dict:
    return session_status(session_id=UUID(session_id))


def _player_status(session_id: str, phone: str) -> str | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.status FROM session_players sp
                JOIN players p ON p.id = sp.player_id
                WHERE sp.session_id = %s AND p.phone = %s
                LIMIT 1
                """,
                (session_id, phone),
            )
            row = cur.fetchone()
    return row["status"] if row else None


def _reach_proposing_state(lead_phone: str, dave_phone: str) -> str:
    """Create a session and have Dave respond with matching prefs, which
    satisfies policy (2 confirmed, overlapping course + time) and triggers
    automatic proposal generation."""
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]
    _sms(dave_phone, "late morning works, bethpage is fine")
    return session_id


def _backdate_invited_at(session_id: str, phone: str, hours_ago: int) -> None:
    backdated = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE session_players sp
                SET invited_at = %s
                FROM players p
                WHERE sp.player_id = p.id
                  AND sp.session_id = %s
                  AND p.phone = %s
                """,
                (backdated, session_id, phone),
            )


# ── scenario 1 ────────────────────────────────────────────────────────────────

def test_01_player_confirms_preferences_via_sms() -> None:
    """Player texts availability → DB status updated to confirmed."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    reply = _sms(dave_phone, "late morning at bethpage works for me")

    assert "updated your preferences" in reply.lower()
    assert _player_status(session_id, dave_phone) == "confirmed"


# ── scenario 2 ────────────────────────────────────────────────────────────────

def test_02_player_declines_via_sms() -> None:
    """Player texts a decline → DB status set to declined."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    reply = _sms(dave_phone, "I'm out this time, sorry")

    assert "marked you as out" in reply.lower()
    assert _player_status(session_id, dave_phone) == "declined"


# ── scenario 3 ────────────────────────────────────────────────────────────────

def test_03_proposals_auto_generated_when_policy_conditions_met() -> None:
    """When the second confirmed player's prefs create an overlap, proposals
    appear automatically and session advances to 'proposing'."""
    lead_phone, dave_phone = _phone(), _phone("929")
    session_id = _reach_proposing_state(lead_phone, dave_phone)

    info = _session_info(session_id)
    assert info["session"]["status"] == "proposing"
    assert len(info["proposals"]) >= 1


# ── scenario 4 ────────────────────────────────────────────────────────────────

def test_04_lead_picks_option_number_requires_explicit_confirm() -> None:
    """Lead texting a number stages the pick but does not execute it —
    the agent asks for CONFIRM <n> before doing anything."""
    lead_phone, dave_phone = _phone(), _phone("929")
    _reach_proposing_state(lead_phone, dave_phone)

    reply = _sms(lead_phone, "1")

    assert "confirm 1" in reply.lower()


# ── scenario 5 ────────────────────────────────────────────────────────────────

def test_05_lead_confirm_locks_session_and_returns_booking_url() -> None:
    """Full pick-and-confirm flow: session reaches 'confirmed', reply
    contains a booking URL for the lead."""
    lead_phone, dave_phone = _phone(), _phone("929")
    session_id = _reach_proposing_state(lead_phone, dave_phone)

    _sms(lead_phone, "1")
    reply = _sms(lead_phone, "CONFIRM 1")

    assert "book here for the group" in reply.lower()
    assert _session_info(session_id)["session"]["status"] == "confirmed"


# ── scenario 6 ────────────────────────────────────────────────────────────────

def test_06_non_lead_cannot_confirm_tee_time() -> None:
    """A non-lead player sending CONFIRM <n> is rejected in code; session
    status does not change."""
    lead_phone, dave_phone = _phone(), _phone("929")
    session_id = _reach_proposing_state(lead_phone, dave_phone)

    reply = _sms(dave_phone, "CONFIRM 1")

    assert "only the lead" in reply.lower()
    assert _session_info(session_id)["session"]["status"] == "proposing"


# ── scenario 7 ────────────────────────────────────────────────────────────────

def test_07_lead_staging_add_player_issues_confirmation_token() -> None:
    """Lead texts 'add <name> <phone>' → action executes immediately and
    new player is invited without an extra confirmation token."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]
    new_phone = _phone("646")

    reply = _sms(lead_phone, f"add Tom {new_phone}")

    assert "player added" in reply.lower()
    assert "confirm action" not in reply.lower()
    assert _player_status(session_id, new_phone) == "invited"


# ── scenario 8 ────────────────────────────────────────────────────────────────

def test_08_lead_remove_player_executes_immediately() -> None:
    """Lead texts 'remove <name>' → player is removed from session immediately,
    no confirmation token required."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    reply = _sms(lead_phone, "remove Dave")

    assert "removed dave" in reply.lower()
    assert "confirm action" not in reply.lower()
    assert _player_status(session_id, dave_phone) is None


# ── scenario 9 ────────────────────────────────────────────────────────────────

def test_09_non_lead_cannot_stage_add_player_action() -> None:
    """A non-lead player texting 'add <name> <phone>' is not treated as
    an admin command — no confirmation token is issued."""
    lead_phone, dave_phone = _phone(), _phone("929")
    _trigger(lead_phone, [("Dave", dave_phone)])
    new_phone = _phone("646")

    reply = _sms(dave_phone, f"add Tom {new_phone}")

    assert "confirm action" not in reply.lower()


# ── scenario 10 ───────────────────────────────────────────────────────────────

def test_10_lead_stages_date_change_with_correct_payload() -> None:
    """Lead texts 'change date to YYYY-MM-DD' → date updates immediately
    without pending confirmation."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    reply = _sms(lead_phone, "change date to 2026-06-15")

    assert "moved to 2026-06-15" in reply.lower()
    assert _session_info(session_id)["session"]["target_date"] == "2026-06-15"


# ── scenario 11 ───────────────────────────────────────────────────────────────

def test_11_confirmed_date_change_resets_session_and_clears_proposals() -> None:
    """Executing a date change resets session to 'collecting', updates the
    target date, clears proposals, and re-polls players."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    # Get Dave to respond so proposals are generated
    _sms(dave_phone, "late morning bethpage")
    assert _session_info(session_id)["session"]["status"] == "proposing"

    # Lead executes the date change directly
    _sms(lead_phone, "change date to 2026-06-15")

    info = _session_info(session_id)
    assert info["session"]["target_date"] == "2026-06-15"
    assert info["session"]["status"] == "collecting"
    assert len(info["proposals"]) == 0


# ── scenario 12 ───────────────────────────────────────────────────────────────

def test_12_no_proposals_when_minimum_group_size_not_met() -> None:
    """If the only invitee declines, confirmed_count stays at 1 (lead only),
    which is below the minimum of 2 — no proposals should be generated."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    _sms(dave_phone, "I'm out, can't make it")

    info = _session_info(session_id)
    assert info["policy"]["minimum_group_size_met"] is False
    assert info["session"]["status"] != "proposing"
    assert len(info["proposals"]) == 0


# ── scenario 13 ───────────────────────────────────────────────────────────────

def test_13_no_proposals_when_no_course_overlap() -> None:
    """If confirmed players have no course in common, has_overlap is False
    and no proposals are generated."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)], courses=["Bethpage", "Marine Park"])
    session_id = result["session_id"]

    # Restrict lead's approved courses to only Bethpage
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE session_players sp
                SET approved_courses = %s
                FROM players p
                WHERE sp.player_id = p.id
                  AND sp.session_id = %s
                  AND p.phone = %s
                """,
                (Jsonb(["Bethpage"]), session_id, lead_phone),
            )

    # Dave confirms with Marine Park only — no intersection with lead's Bethpage
    _sms(dave_phone, "marine park works, late morning")

    info = _session_info(session_id)
    assert info["policy"]["has_overlap"] is False
    assert len(info["proposals"]) == 0


# ── scenario 14 ───────────────────────────────────────────────────────────────

def test_14_reminder_sent_after_4_hours_of_no_response() -> None:
    """Reminder job fires for a player who was invited 5 hours ago and has
    not responded — reminder_sent_at is stamped, status stays 'invited'."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    _backdate_invited_at(session_id, dave_phone, hours_ago=5)

    cycle = run_reminder_cycle(now=datetime.now(timezone.utc))
    assert cycle["reminded"] >= 1

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.status, sp.reminder_sent_at FROM session_players sp
                JOIN players p ON p.id = sp.player_id
                WHERE sp.session_id = %s AND p.phone = %s
                """,
                (session_id, dave_phone),
            )
            row = cur.fetchone()

    assert row["reminder_sent_at"] is not None
    assert row["status"] == "invited"  # reminder only, not yet escalated


# ── scenario 15 ───────────────────────────────────────────────────────────────

def test_15_escalation_after_8_hours_marks_player_unresponsive() -> None:
    """Escalation job fires for a player invited 9 hours ago — player is
    marked unresponsive and lead receives an escalation message."""
    lead_phone, dave_phone = _phone(), _phone("929")
    result = _trigger(lead_phone, [("Dave", dave_phone)])
    session_id = result["session_id"]

    _backdate_invited_at(session_id, dave_phone, hours_ago=9)

    cycle = run_reminder_cycle(now=datetime.now(timezone.utc))
    assert cycle["escalated"] >= 1

    assert _player_status(session_id, dave_phone) == "unresponsive"
