from __future__ import annotations

import os
import random
from datetime import date, timedelta
from uuid import uuid4

import pytest

from db import get_conn
from main import (
    LeadInvitee,
    LeadTriggerPayload,
    _process_inbound_sms,
    lead_trigger,
    session_status,
)


def _random_us_phone(prefix: str) -> str:
    return f"+1{prefix}{random.randint(1000000, 9999999)}"


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION_TESTS", "0") != "1",
    reason="Set RUN_DB_INTEGRATION_TESTS=1 to run DB-backed integration tests.",
)


def test_end_to_end_proposal_and_confirm_flow() -> None:
    lead_phone = _random_us_phone("917")
    invite_phone = _random_us_phone("929")
    target_date = date.today() + timedelta(days=7)

    created = lead_trigger(
        LeadTriggerPayload(
            lead_phone=lead_phone,
            lead_name="Integration Lead",
            target_date=target_date,
            candidate_courses=["Bethpage", "Marine Park"],
            invitees=[LeadInvitee(name="Integration Dave", phone=invite_phone)],
            send_invites=False,
        )
    )
    session_id = created["session_id"]

    invite_reply = _process_inbound_sms(
        {
            "From": invite_phone,
            "Body": "late morning works at bethpage",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert "updated your preferences" in invite_reply.lower()

    status_payload = session_status(session_id=session_id)
    assert status_payload["ok"] is True
    assert status_payload["session"]["status"] in ("proposing", "searching")
    assert len(status_payload["proposals"]) >= 1

    lead_pick_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": "1",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert "confirm 1" in lead_pick_reply.lower()

    lead_confirm_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": "CONFIRM 1",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert "book here for the group" in lead_confirm_reply.lower()

    final_status_payload = session_status(session_id=session_id)
    assert final_status_payload["session"]["status"] == "confirmed"


def test_lead_action_add_player_flow() -> None:
    lead_phone = _random_us_phone("917")
    invite_phone = _random_us_phone("929")
    new_player_phone = _random_us_phone("646")
    target_date = date.today() + timedelta(days=10)

    created = lead_trigger(
        LeadTriggerPayload(
            lead_phone=lead_phone,
            lead_name="Integration Lead",
            target_date=target_date,
            candidate_courses=["Bethpage", "Marine Park"],
            invitees=[LeadInvitee(name="Integration Dave", phone=invite_phone)],
            send_invites=False,
        )
    )
    session_id = created["session_id"]

    add_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": f"add Tom {new_player_phone}",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert "player added" in add_reply.lower()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.status, p.name, p.phone
                FROM session_players sp
                JOIN players p ON p.id = sp.player_id
                WHERE sp.session_id = %s AND p.phone = %s
                LIMIT 1
                """,
                (session_id, new_player_phone),
            )
            joined = cur.fetchone()

    assert joined is not None
    assert joined["status"] == "invited"
    assert joined["name"] == "Tom"


def test_lead_action_change_date_flow() -> None:
    lead_phone = _random_us_phone("917")
    invite_phone = _random_us_phone("929")
    target_date = date.today() + timedelta(days=9)
    new_target_date = date.today() + timedelta(days=14)

    created = lead_trigger(
        LeadTriggerPayload(
            lead_phone=lead_phone,
            lead_name="Integration Lead",
            target_date=target_date,
            candidate_courses=["Bethpage", "Marine Park"],
            invitees=[LeadInvitee(name="Integration Dave", phone=invite_phone)],
            send_invites=False,
        )
    )
    session_id = created["session_id"]

    change_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": f"change date to {new_target_date.isoformat()}",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert f"moved to {new_target_date.isoformat()}" in change_reply.lower()

    status_payload = session_status(session_id=session_id)
    assert status_payload["session"]["target_date"] == new_target_date.isoformat()
    assert status_payload["session"]["status"] == "collecting"


def test_lead_action_remove_player_flow() -> None:
    lead_phone = _random_us_phone("917")
    invite_phone = _random_us_phone("929")
    target_date = date.today() + timedelta(days=11)

    created = lead_trigger(
        LeadTriggerPayload(
            lead_phone=lead_phone,
            lead_name="Integration Lead",
            target_date=target_date,
            candidate_courses=["Bethpage", "Marine Park"],
            invitees=[LeadInvitee(name="Integration Dave", phone=invite_phone)],
            send_invites=False,
        )
    )
    session_id = created["session_id"]

    remove_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": "remove Integration Dave",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert "removed integration dave" in remove_reply.lower()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.id
                FROM session_players sp
                JOIN players p ON p.id = sp.player_id
                WHERE sp.session_id = %s AND p.phone = %s
                """,
                (session_id, invite_phone),
            )
            removed_row = cur.fetchone()
    assert removed_row is None


def test_lead_action_change_courses_flow() -> None:
    lead_phone = _random_us_phone("917")
    invite_phone = _random_us_phone("929")
    target_date = date.today() + timedelta(days=12)
    new_courses = ["Maple Moor", "Saxon Woods"]

    created = lead_trigger(
        LeadTriggerPayload(
            lead_phone=lead_phone,
            lead_name="Integration Lead",
            target_date=target_date,
            candidate_courses=["Bethpage", "Marine Park"],
            invitees=[LeadInvitee(name="Integration Dave", phone=invite_phone)],
            send_invites=False,
        )
    )
    session_id = created["session_id"]

    change_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": f"change courses: {', '.join(new_courses)}",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert "candidate courses updated" in change_reply.lower()

    status_payload = session_status(session_id=session_id)
    assert status_payload["session"]["candidate_courses"] == new_courses
    assert status_payload["session"]["status"] == "collecting"
