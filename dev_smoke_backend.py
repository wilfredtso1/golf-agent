from __future__ import annotations

import random
from datetime import date, timedelta
from uuid import UUID

from db import get_conn
from main import (
    FormResponsePayload,
    LeadInvitee,
    LeadTriggerPayload,
    get_form_context,
    lead_trigger,
    submit_form_response,
)
from token_utils import generate_form_token


def _random_us_phone(prefix: str) -> str:
    return f"+1{prefix}{random.randint(1000000, 9999999)}"


def run_smoke() -> None:
    lead_phone = _random_us_phone("917")
    invite_phone = _random_us_phone("929")
    target_date = date.today() + timedelta(days=7)

    created = lead_trigger(
        LeadTriggerPayload(
            lead_phone=lead_phone,
            lead_name="Smoke Lead",
            target_date=target_date,
            candidate_courses=["Bethpage", "Marine Park"],
            invitees=[LeadInvitee(name="Smoke Player", phone=invite_phone)],
            send_invites=False,
        )
    )

    session_id = UUID(created["session_id"])

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM players WHERE phone = %s", (invite_phone,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Smoke test failed: invitee player was not created")
            player_id = row["id"]

    token = generate_form_token(str(session_id), str(player_id))
    context = get_form_context(token)
    if context["session_id"] != str(session_id):
        raise RuntimeError("Smoke test failed: form context returned wrong session")

    submit_result = submit_form_response(
        FormResponsePayload(
            token=token,
            is_attending=True,
            approved_courses=["Bethpage"],
            available_time_blocks=["late_morning"],
        )
    )

    print("SMOKE_BACKEND_OK")
    print(f"session_id={submit_result['session_id']}")
    print(f"player_id={submit_result['player_id']}")
    print(f"status={submit_result['status']}")


if __name__ == "__main__":
    run_smoke()
