from __future__ import annotations

import os
import random
from datetime import date, timedelta
from uuid import uuid4

import pytest

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

