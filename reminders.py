from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db import get_conn
from twilio_helpers import send_sms

REMINDER_AFTER_HOURS = 4
ESCALATE_AFTER_HOURS = 8


def classify_reminder_action(
    invited_at: datetime,
    reminder_sent_at: datetime | None,
    now: datetime,
) -> str:
    elapsed = now - invited_at
    if elapsed >= timedelta(hours=ESCALATE_AFTER_HOURS):
        return "escalate"
    if elapsed >= timedelta(hours=REMINDER_AFTER_HOURS) and reminder_sent_at is None:
        return "remind"
    return "none"


def run_reminder_cycle(now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    reminded = 0
    escalated = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  sp.id AS session_player_id,
                  sp.session_id,
                  sp.player_id,
                  sp.invited_at,
                  sp.reminder_sent_at,
                  p.name AS player_name,
                  p.phone AS player_phone,
                  lead.id AS lead_player_id,
                  lead.name AS lead_name,
                  lead.phone AS lead_phone,
                  s.target_date
                FROM session_players sp
                JOIN sessions s ON s.id = sp.session_id
                JOIN players p ON p.id = sp.player_id
                JOIN players lead ON lead.id = s.lead_player_id
                WHERE s.status = ANY(%s)
                  AND sp.status = 'invited'
                ORDER BY sp.invited_at ASC
                """,
                (["collecting", "searching", "proposing"],),
            )
            rows = cur.fetchall()

            for row in rows:
                action = classify_reminder_action(row["invited_at"], row["reminder_sent_at"], now)
                if action == "none":
                    continue

                if action == "remind":
                    reminder_body = (
                        f"Hey {row['player_name']}, this is Golf Agent. "
                        f"{row['lead_name']} is trying to lock down golf for {row['target_date'].isoformat()}. "
                        "Please send your availability or use your form link."
                    )
                    sid = _safe_send_sms(row["player_phone"], reminder_body)
                    _insert_outbound_message(
                        cur,
                        session_id=row["session_id"],
                        player_id=row["player_id"],
                        body=reminder_body,
                        provider_message_sid=sid,
                    )
                    cur.execute(
                        "UPDATE session_players SET reminder_sent_at = %s WHERE id = %s",
                        (now, row["session_player_id"]),
                    )
                    reminded += 1
                    continue

                escalate_body = (
                    f"Heads up: still no response from {row['player_name']} after {ESCALATE_AFTER_HOURS} hours. "
                    "Reply with PROCEED WITHOUT THEM if you want to move forward."
                )
                sid = _safe_send_sms(row["lead_phone"], escalate_body)
                _insert_outbound_message(
                    cur,
                    session_id=row["session_id"],
                    player_id=row["lead_player_id"],
                    body=escalate_body,
                    provider_message_sid=sid,
                )
                cur.execute(
                    """
                    UPDATE session_players
                    SET status = 'unresponsive', reminder_sent_at = COALESCE(reminder_sent_at, %s)
                    WHERE id = %s
                    """,
                    (now, row["session_player_id"]),
                )
                escalated += 1

    return {"reminded": reminded, "escalated": escalated}


def _safe_send_sms(phone: str, body: str) -> str | None:
    try:
        return send_sms(phone, body)
    except Exception:  # pragma: no cover - provider/network failures
        return None


def _insert_outbound_message(
    cur,
    *,
    session_id,
    player_id,
    body: str,
    provider_message_sid: str | None,
) -> None:
    cur.execute(
        """
        INSERT INTO messages (session_id, player_id, direction, body, provider_message_sid)
        VALUES (%s, %s, 'outbound', %s, %s)
        """,
        (session_id, player_id, body, provider_message_sid),
    )
