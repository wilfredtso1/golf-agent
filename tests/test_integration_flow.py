from __future__ import annotations

import os
import random
import re
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


def test_lead_action_stage_and_confirm_add_player_flow() -> None:
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

    stage_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": f"add Tom {new_player_phone}",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    token_match = re.search(r"CONFIRM ACTION (act-[a-f0-9]{6})", stage_reply, flags=re.IGNORECASE)
    assert token_match, f"Expected confirmation token in reply, got: {stage_reply}"
    token = token_match.group(1).lower()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT action_type, payload, consumed_at
                FROM pending_confirmations
                WHERE token = %s
                """,
                (token,),
            )
            pending = cur.fetchone()
    assert pending is not None
    assert pending["action_type"] == "add_player"
    assert pending["payload"]["phone"] == new_player_phone
    assert pending["consumed_at"] is None

    confirm_reply = _process_inbound_sms(
        {
            "From": lead_phone,
            "Body": f"CONFIRM ACTION {token}",
            "MessageSid": f"itest-{uuid4().hex}",
        }
    )
    assert "player added" in confirm_reply.lower()

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

            cur.execute(
                """
                SELECT consumed_at
                FROM pending_confirmations
                WHERE token = %s
                """,
                (token,),
            )
            consumed = cur.fetchone()

    assert joined is not None
    assert joined["status"] == "invited"
    assert joined["name"] == "Tom"
    assert consumed is not None
    assert consumed["consumed_at"] is not None
