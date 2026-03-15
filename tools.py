from __future__ import annotations

import logging
from datetime import date
from typing import Optional
from uuid import UUID

from psycopg.types.json import Jsonb

logger = logging.getLogger("golf-agent")


def _get_session_status(cur, session_id: UUID) -> str | None:
    cur.execute("SELECT status FROM sessions WHERE id = %s LIMIT 1", (session_id,))
    row = cur.fetchone()
    return row["status"] if row else None


def upsert_course_snapshot(
    cur,
    *,
    name: str,
    booking_url: str | None,
    price_per_player: float | None,
    currency: str = "USD",
    metadata: dict[str, object] | None = None,
) -> None:
    clean_name = name.strip()
    if not clean_name:
        return
    payload: dict[str, object] = {"source": "proposal_generation"}
    if metadata:
        payload.update(metadata)
    cur.execute(
        """
        INSERT INTO courses (
          name,
          default_booking_url,
          latest_price_per_player,
          latest_currency,
          latest_seen_at,
          metadata
        )
        VALUES (%s, %s, %s, %s, now(), %s)
        ON CONFLICT (name) DO UPDATE
        SET default_booking_url = EXCLUDED.default_booking_url,
            latest_price_per_player = EXCLUDED.latest_price_per_player,
            latest_currency = EXCLUDED.latest_currency,
            latest_seen_at = now(),
            metadata = courses.metadata || EXCLUDED.metadata,
            updated_at = now()
        """,
        (
            clean_name,
            booking_url,
            price_per_player,
            currency,
            Jsonb(payload),
        ),
    )


def list_courses(cur, *, query: str | None = None, limit: int = 100) -> list[dict[str, object]]:
    if query and query.strip():
        cur.execute(
            """
            SELECT
              id,
              name,
              default_booking_url,
              latest_price_per_player,
              latest_currency,
              latest_seen_at,
              metadata,
              created_at,
              updated_at
            FROM courses
            WHERE name ILIKE %s
            ORDER BY name ASC
            LIMIT %s
            """,
            (f"%{query.strip()}%", max(1, min(limit, 500))),
        )
    else:
        cur.execute(
            """
            SELECT
              id,
              name,
              default_booking_url,
              latest_price_per_player,
              latest_currency,
              latest_seen_at,
              metadata,
              created_at,
              updated_at
            FROM courses
            ORDER BY name ASC
            LIMIT %s
            """,
            (max(1, min(limit, 500)),),
        )
    return cur.fetchall()


def get_player_profile(cur, player_id: UUID) -> dict[str, object] | None:
    cur.execute(
        """
        SELECT id, name, phone, general_availability, course_preferences, standing_constraints
        FROM players
        WHERE id = %s
        LIMIT 1
        """,
        (player_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "general_availability": row["general_availability"] or [],
        "course_preferences": row["course_preferences"] or [],
        "standing_constraints": row["standing_constraints"],
    }


def get_player_name(cur, player_id: UUID) -> str:
    cur.execute("SELECT name FROM players WHERE id = %s LIMIT 1", (player_id,))
    row = cur.fetchone()
    return (row["name"] if row else "Player") or "Player"


def get_session_state(cur, session_id: UUID) -> dict[str, object] | None:
    cur.execute(
        """
        SELECT id, lead_player_id, target_date, candidate_courses, session_code, status
        FROM sessions
        WHERE id = %s
        LIMIT 1
        """,
        (session_id,),
    )
    session = cur.fetchone()
    if not session:
        return None

    cur.execute(
        """
        SELECT
          sp.player_id,
          sp.status,
          sp.available_time_blocks,
          sp.approved_courses,
          sp.invited_at,
          sp.responded_at,
          p.name,
          p.phone
        FROM session_players sp
        JOIN players p ON p.id = sp.player_id
        WHERE sp.session_id = %s
        ORDER BY sp.invited_at ASC
        """,
        (session_id,),
    )
    players = cur.fetchall()

    return {
        "id": session["id"],
        "lead_player_id": session["lead_player_id"],
        "target_date": session["target_date"],
        "candidate_courses": session["candidate_courses"] or [],
        "session_code": session.get("session_code"),
        "status": session["status"],
        "players": [
            {
                "player_id": row["player_id"],
                "name": row["name"],
                "phone": row["phone"],
                "status": row["status"],
                "available_time_blocks": row["available_time_blocks"] or [],
                "approved_courses": row["approved_courses"] or [],
                "invited_at": row["invited_at"],
                "responded_at": row["responded_at"],
            }
            for row in players
        ],
    }


def get_player_session_state(cur, session_id: UUID, player_id: UUID) -> dict[str, object] | None:
    cur.execute(
        """
        SELECT status, available_time_blocks, approved_courses
        FROM session_players
        WHERE session_id = %s AND player_id = %s
        LIMIT 1
        """,
        (session_id, player_id),
    )
    row = cur.fetchone()
    if not row:
        return None

    return {
        "status": row["status"],
        "available_time_blocks": row["available_time_blocks"] or [],
        "approved_courses": row["approved_courses"] or [],
    }


def get_recent_messages(cur, session_id: UUID | None, player_id: UUID, limit: int = 10) -> list[dict[str, object]]:
    bounded_limit = max(1, min(limit, 200))
    if session_id is None:
        cur.execute(
            """
            SELECT direction, body, created_at
            FROM messages
            WHERE player_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (player_id, bounded_limit),
        )
    else:
        cur.execute(
            """
            SELECT direction, body, created_at
            FROM messages
            WHERE player_id = %s
              AND session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (player_id, session_id, bounded_limit),
        )
    rows = cur.fetchall()
    rows.reverse()
    return [
        {
            "direction": row["direction"],
            "body": row["body"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_session_players(cur, session_id: UUID) -> list[dict[str, object]]:
    cur.execute(
        """
        SELECT sp.player_id, p.name, p.phone, sp.status
        FROM session_players sp
        JOIN players p ON p.id = sp.player_id
        WHERE sp.session_id = %s
        ORDER BY sp.invited_at ASC
        """,
        (session_id,),
    )
    return [
        {
            "player_id": row["player_id"],
            "name": row["name"],
            "phone": row["phone"],
            "status": row["status"],
        }
        for row in cur.fetchall()
    ]


def ensure_session_proposals(
    cur,
    session: dict[str, object],
    policy: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    from booking_provider import search_tee_times
    from policy_engine import evaluate_session

    active_policy = policy or evaluate_session(session)
    if not (active_policy["minimum_group_size_met"] and active_policy["has_overlap"]):
        return []

    target_date = session.get("target_date")
    if target_date is None:
        return []

    options = search_tee_times(
        target_date=target_date,
        time_windows=list(active_policy["time_overlap"]),
        courses=list(active_policy["course_overlap"]),
        group_size=int(active_policy["confirmed_count"]),
    )
    if not options:
        return []

    proposals = replace_tee_time_proposals(cur, session["id"], options)
    update_session_status(cur, session["id"], "proposing")
    return proposals


def replace_tee_time_proposals(cur, session_id: UUID, options: list[dict[str, object]]) -> list[dict[str, object]]:
    cur.execute("DELETE FROM tee_time_proposals WHERE session_id = %s", (session_id,))

    created: list[dict[str, object]] = []
    for option in options:
        upsert_course_snapshot(
            cur,
            name=str(option["course"]),
            booking_url=option.get("booking_url"),
            price_per_player=float(option["price_per_player"]) if option.get("price_per_player") is not None else None,
        )
        cur.execute(
            """
            INSERT INTO tee_time_proposals (session_id, course, tee_time, price_per_player, booking_url, status)
            VALUES (%s, %s, %s, %s, %s, 'proposed')
            RETURNING id, course, tee_time, price_per_player, booking_url, status
            """,
            (
                session_id,
                option["course"],
                option["tee_time"],
                option.get("price_per_player"),
                option.get("booking_url"),
            ),
        )
        created.append(cur.fetchone())
    return created


def get_latest_proposals(cur, session_id: UUID) -> list[dict[str, object]]:
    cur.execute(
        """
        SELECT id, course, tee_time, price_per_player, booking_url, status
        FROM tee_time_proposals
        WHERE session_id = %s
        ORDER BY created_at ASC
        """,
        (session_id,),
    )
    return cur.fetchall()


def select_proposal_by_position(cur, session_id: UUID, one_based_position: int) -> dict[str, object] | None:
    proposals = get_latest_proposals(cur, session_id)
    if one_based_position < 1 or one_based_position > len(proposals):
        return None

    selected = proposals[one_based_position - 1]
    cur.execute("UPDATE tee_time_proposals SET status = 'expired' WHERE session_id = %s", (session_id,))
    cur.execute("UPDATE tee_time_proposals SET status = 'selected' WHERE id = %s", (selected["id"],))
    return selected


def update_session_player(
    cur,
    session_id: UUID,
    player_id: UUID,
    *,
    status: Optional[str] = None,
    approved_courses: Optional[list[str]] = None,
    available_time_blocks: Optional[list[str]] = None,
) -> None:
    previous_status: str | None = None
    if status is not None:
        cur.execute(
            "SELECT status FROM session_players WHERE session_id = %s AND player_id = %s LIMIT 1",
            (session_id, player_id),
        )
        row = cur.fetchone()
        previous_status = row["status"] if row else None

    updates: list[str] = []
    values: list[object] = []

    if status is not None:
        updates.append("status = %s")
        values.append(status)

    if approved_courses is not None:
        updates.append("approved_courses = %s")
        values.append(Jsonb(approved_courses))

    if available_time_blocks is not None:
        updates.append("available_time_blocks = %s")
        values.append(Jsonb(available_time_blocks))

    if status is not None or approved_courses is not None or available_time_blocks is not None:
        updates.append("responded_at = now()")

    if not updates:
        return

    values.extend([session_id, player_id])
    cur.execute(
        f"UPDATE session_players SET {', '.join(updates)} WHERE session_id = %s AND player_id = %s",
        tuple(values),
    )
    if status is not None and previous_status != status:
        logger.info(
            "player_status_transition session_id=%s player_id=%s from=%s to=%s source=update_session_player",
            session_id,
            player_id,
            previous_status,
            status,
        )


def update_session_status(cur, session_id: UUID, status: str) -> None:
    previous_status = _get_session_status(cur, session_id)
    cur.execute("UPDATE sessions SET status = %s WHERE id = %s", (status, session_id))
    if previous_status != status:
        logger.info(
            "session_status_transition session_id=%s from=%s to=%s source=update_session_status",
            session_id,
            previous_status,
            status,
        )


def add_or_get_player_by_phone(cur, *, phone: str, name: str) -> UUID:
    cur.execute("SELECT id, name FROM players WHERE phone = %s", (phone,))
    existing = cur.fetchone()
    if existing:
        existing_name = existing["name"] or ""
        if name.strip() and existing_name.startswith("Player "):
            cur.execute("UPDATE players SET name = %s WHERE id = %s", (name.strip(), existing["id"]))
        return existing["id"]

    cur.execute(
        """
        INSERT INTO players (name, phone)
        VALUES (%s, %s)
        RETURNING id
        """,
        (name.strip() or f"Player {phone[-4:]}", phone),
    )
    row = cur.fetchone()
    return row["id"]


def add_player_to_session(cur, *, session_id: UUID, player_id: UUID) -> bool:
    cur.execute(
        """
        INSERT INTO session_players (session_id, player_id, status)
        VALUES (%s, %s, 'invited')
        ON CONFLICT (session_id, player_id) DO NOTHING
        RETURNING id
        """,
        (session_id, player_id),
    )
    return cur.fetchone() is not None


def remove_player_from_session_by_name(cur, *, session_id: UUID, name: str) -> bool:
    cur.execute(
        """
        DELETE FROM session_players sp
        USING players p
        WHERE sp.player_id = p.id
          AND sp.session_id = %s
          AND lower(p.name) = lower(%s)
        RETURNING sp.id
        """,
        (session_id, name.strip()),
    )
    return cur.fetchone() is not None


def update_session_date(cur, *, session_id: UUID, target_date: date) -> None:
    previous_status = _get_session_status(cur, session_id)
    cur.execute("UPDATE sessions SET target_date = %s, status = 'collecting' WHERE id = %s", (target_date, session_id))
    if previous_status != "collecting":
        logger.info(
            "session_status_transition session_id=%s from=%s to=collecting source=update_session_date",
            session_id,
            previous_status,
        )
    cur.execute(
        """
        UPDATE session_players
        SET status = CASE WHEN status = 'declined' THEN 'declined' ELSE 'invited' END,
            approved_courses = '[]'::jsonb,
            available_time_blocks = '[]'::jsonb,
            responded_at = NULL,
            reminder_sent_at = NULL
        WHERE session_id = %s
        """,
        (session_id,),
    )
    cur.execute("DELETE FROM tee_time_proposals WHERE session_id = %s", (session_id,))


def update_session_courses(cur, *, session_id: UUID, candidate_courses: list[str]) -> None:
    previous_status = _get_session_status(cur, session_id)
    cur.execute(
        "UPDATE sessions SET candidate_courses = %s, status = 'collecting' WHERE id = %s",
        (Jsonb(candidate_courses), session_id),
    )
    if previous_status != "collecting":
        logger.info(
            "session_status_transition session_id=%s from=%s to=collecting source=update_session_courses",
            session_id,
            previous_status,
        )
    cur.execute(
        """
        UPDATE session_players
        SET status = CASE WHEN status = 'declined' THEN 'declined' ELSE 'invited' END,
            approved_courses = '[]'::jsonb,
            available_time_blocks = '[]'::jsonb,
            responded_at = NULL,
            reminder_sent_at = NULL
        WHERE session_id = %s
        """,
        (session_id,),
    )
    cur.execute("DELETE FROM tee_time_proposals WHERE session_id = %s", (session_id,))


def insert_outbound_message(
    cur,
    *,
    session_id: UUID | None,
    player_id: UUID,
    body: str,
    provider_message_sid: str | None = None,
) -> None:
    """Persist an outbound message. Consolidated from main.py and reminders.py."""
    cur.execute(
        """
        INSERT INTO messages (session_id, player_id, direction, body, provider_message_sid)
        VALUES (%s, %s, 'outbound', %s, %s)
        """,
        (session_id, player_id, body, provider_message_sid),
    )
