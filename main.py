from __future__ import annotations

import logging
import random
import re
from datetime import date
from typing import Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from psycopg import errors
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field
from twilio.twiml.messaging_response import MessagingResponse

from agent import process_inbound_message
from config import SETTINGS
from context_builder import build_context
from db import get_conn
from policy_engine import evaluate_session
from token_utils import InvalidFormToken, build_form_url, generate_form_token, verify_form_token
from tools import (
    ensure_session_proposals,
    get_latest_proposals,
    insert_outbound_message,
    list_courses,
    get_session_state,
    list_session_players,
    upsert_course_snapshot,
)
from twilio_helpers import InvalidPhoneNumber, normalize_phone, send_sms, validate_twilio_signature
from reminders import run_reminder_cycle

logger = logging.getLogger("golf-agent")
logging.basicConfig(level=logging.INFO)

ACTIVE_SESSION_STATUSES = ("collecting", "searching", "proposing")
DEFAULT_TIME_BLOCKS = ["early_morning", "late_morning", "early_afternoon"]
ALLOWED_TIME_BLOCKS = frozenset(DEFAULT_TIME_BLOCKS)
_SESSION_CODE_INSERT_MAX_ATTEMPTS = 8
_SESSION_CODE_PREFIX_RE = re.compile(r"^\s*(\d{2,4})\s*[:\-]?\s*(.*)$")
_SESSION_CODE_INLINE_RE = re.compile(r"\b(?:session|for)\s+(\d{2,4})\b", re.IGNORECASE)

app = FastAPI(title="Golf Agent", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(SETTINGS.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class PlayerProfileUpdate(BaseModel):
    name: Optional[str] = None
    general_availability: list[str] = Field(default_factory=list)
    course_preferences: list[str] = Field(default_factory=list)
    standing_constraints: Optional[str] = None


class FormResponsePayload(BaseModel):
    token: str = Field(..., json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."})
    is_attending: bool = Field(..., json_schema_extra={"example": True})
    approved_courses: list[str] = Field(default_factory=list, json_schema_extra={"example": ["Maple Moor"]})
    available_time_blocks: list[str] = Field(default_factory=list, json_schema_extra={"example": ["late_morning"]})
    player_profile: Optional[PlayerProfileUpdate] = None


class LeadInvitee(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Dave"})
    phone: str = Field(..., json_schema_extra={"example": "+19175550123"})


class LeadTriggerPayload(BaseModel):
    lead_phone: str = Field(..., json_schema_extra={"example": "+19175550100"})
    lead_name: Optional[str] = Field(default=None, json_schema_extra={"example": "Will"})
    target_date: date = Field(..., json_schema_extra={"example": "2026-03-15"})
    candidate_courses: list[str] = Field(
        default_factory=list,
        json_schema_extra={"example": ["Maple Moor", "Silver Lake"]},
    )
    invitees: list[LeadInvitee] = Field(default_factory=list)
    send_invites: bool = Field(default=True, json_schema_extra={"example": False})


class DevSimulateSmsPayload(BaseModel):
    from_number: str
    body: str = ""
    message_sid: str = Field(default_factory=lambda: f"dev-{uuid4().hex}")


def _clean_non_empty_strings(raw_values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in raw_values:
        trimmed = value.strip()
        if trimmed:
            cleaned.append(trimmed)
    return cleaned


def _validated_form_preferences(
    *,
    is_attending: bool,
    approved_courses: list[str],
    available_time_blocks: list[str],
    candidate_courses: list[str],
) -> tuple[list[str], list[str]]:
    if not is_attending:
        return [], []

    cleaned_courses = _clean_non_empty_strings(approved_courses)
    cleaned_time_blocks = _clean_non_empty_strings(available_time_blocks)

    if not cleaned_courses:
        raise HTTPException(status_code=400, detail="At least one approved course is required when attending")
    if not cleaned_time_blocks:
        raise HTTPException(status_code=400, detail="At least one available time block is required when attending")

    invalid_time_blocks = sorted({slot for slot in cleaned_time_blocks if slot not in ALLOWED_TIME_BLOCKS})
    if invalid_time_blocks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time blocks: {', '.join(invalid_time_blocks)}",
        )

    course_lookup = {course.lower(): course for course in candidate_courses if isinstance(course, str)}
    invalid_courses = sorted({course for course in cleaned_courses if course.lower() not in course_lookup})
    if invalid_courses:
        raise HTTPException(
            status_code=400,
            detail=f"Approved courses must be from session candidates. Invalid: {', '.join(invalid_courses)}",
        )

    normalized_courses = [course_lookup[course.lower()] for course in cleaned_courses]
    return normalized_courses, cleaned_time_blocks


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/courses")
def courses(q: Optional[str] = None, limit: int = 100) -> dict[str, object]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            rows = list_courses(cur, query=q, limit=limit)
    return {
        "ok": True,
        "count": len(rows),
        "courses": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "default_booking_url": row["default_booking_url"],
                "latest_price_per_player": float(row["latest_price_per_player"]) if row["latest_price_per_player"] is not None else None,
                "latest_currency": row["latest_currency"],
                "latest_seen_at": row["latest_seen_at"].isoformat() if row["latest_seen_at"] else None,
                "metadata": row["metadata"] or {},
            }
            for row in rows
        ],
    }


@app.post("/jobs/reminders")
def run_reminders_job() -> dict[str, object]:
    result = run_reminder_cycle()
    return {"ok": True, **result}


@app.get(
    "/api/session-status",
    summary="Get session status, policy overlap, players, and proposals",
    response_description="Current session state and matching proposals",
)
def session_status(session_id: UUID) -> dict[str, object]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            session = get_session_state(cur, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            policy = evaluate_session(session)
            proposals = get_latest_proposals(cur, session_id)
            return {
                "ok": True,
                "session": {
                    "id": str(session["id"]),
                    "session_code": session.get("session_code"),
                    "status": session["status"],
                    "target_date": session["target_date"].isoformat(),
                    "candidate_courses": session["candidate_courses"],
                },
                "policy": policy,
                "players": [
                    {
                        "player_id": str(player["player_id"]),
                        "name": player["name"],
                        "status": player["status"],
                        "available_time_blocks": player["available_time_blocks"],
                        "approved_courses": player["approved_courses"],
                    }
                    for player in session["players"]
                ],
                "proposals": [
                    {
                        "id": str(item["id"]),
                        "course": item["course"],
                        "tee_time": item["tee_time"].isoformat(),
                        "price_per_player": float(item["price_per_player"]) if item["price_per_player"] is not None else None,
                        "status": item["status"],
                    }
                    for item in proposals
                ],
            }


@app.post(
    "/api/lead-trigger",
    summary="Create a session and invite players",
    response_description="Session creation result and invite send results",
)
def lead_trigger(payload: LeadTriggerPayload) -> dict[str, object]:
    cleaned_courses = [course.strip() for course in payload.candidate_courses if course.strip()]
    if not cleaned_courses:
        raise HTTPException(status_code=400, detail="At least one candidate course is required")
    if not payload.invitees:
        raise HTTPException(status_code=400, detail="At least one invitee is required")

    try:
        lead_phone = normalize_phone(payload.lead_phone)
    except InvalidPhoneNumber as exc:
        raise HTTPException(status_code=400, detail=f"Invalid lead phone: {exc}") from exc

    invite_targets: list[dict[str, object]] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            lead_player_id = _get_or_create_player(cur, lead_phone, payload.lead_name)
            for course in cleaned_courses:
                upsert_course_snapshot(
                    cur,
                    name=course,
                    booking_url=None,
                    price_per_player=None,
                )
            session_id, session_code = _create_session_with_unique_code(
                cur,
                lead_player_id=lead_player_id,
                target_date=payload.target_date,
                candidate_courses=cleaned_courses,
            )

            cur.execute(
                """
                INSERT INTO session_players (
                  session_id,
                  player_id,
                  status,
                  approved_courses,
                  available_time_blocks,
                  responded_at
                )
                VALUES (%s, %s, 'confirmed', %s, %s, now())
                ON CONFLICT (session_id, player_id) DO NOTHING
                """,
                (session_id, lead_player_id, Jsonb(cleaned_courses), Jsonb(DEFAULT_TIME_BLOCKS)),
            )

            for invitee in payload.invitees:
                try:
                    invitee_phone = normalize_phone(invitee.phone)
                except InvalidPhoneNumber as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid invitee phone for {invitee.name}: {exc}") from exc

                player_id = _get_or_create_player(cur, invitee_phone, invitee.name)
                cur.execute(
                    """
                    INSERT INTO session_players (session_id, player_id, status)
                    VALUES (%s, %s, 'invited')
                    ON CONFLICT (session_id, player_id) DO NOTHING
                    """,
                    (session_id, player_id),
                )
                invite_targets.append(
                    {
                        "player_id": player_id,
                        "name": invitee.name.strip() or f"Player {invitee_phone[-4:]}",
                        "phone": invitee_phone,
                    }
                )

    invite_results: list[dict[str, str]] = []
    if payload.send_invites:
        outbound_logs: list[tuple[UUID, UUID, str, str]] = []
        for target in invite_targets:
            token = generate_form_token(str(session_id), str(target["player_id"]))
            form_link = build_form_url(token)
            message_body = (
                f"Hey {target['name']}, this is Golf Agent helping "
                f"{payload.lead_name or 'your lead'} coordinate a round on {payload.target_date.isoformat()} "
                f"(Session {session_code}). "
                f"Please submit your availability: {form_link}"
            )
            try:
                provider_sid = send_sms(str(target["phone"]), message_body)
                outbound_logs.append((session_id, target["player_id"], message_body, provider_sid))
                invite_results.append(
                    {"phone": str(target["phone"]), "status": "sent", "message_sid": provider_sid}
                )
            except Exception as exc:  # pragma: no cover - network/provider failures
                # Mask phone to last 4 digits — full numbers must not appear in stored logs.
                logger.exception("Failed to send invite SMS to ***%s", str(target["phone"])[-4:])
                invite_results.append(
                    {"phone": str(target["phone"]), "status": "failed", "error": str(exc)}
                )

        if outbound_logs:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    for queued_session_id, queued_player_id, body, provider_sid in outbound_logs:
                        insert_outbound_message(
                            cur,
                            session_id=queued_session_id,
                            player_id=queued_player_id,
                            body=body,
                            provider_message_sid=provider_sid,
                        )

    return {
        "ok": True,
        "session_id": str(session_id),
        "session_code": session_code,
        "invite_count": len(invite_targets),
        "invites": invite_results,
    }


@app.post("/webhooks/twilio/sms")
async def twilio_sms_webhook(request: Request) -> Response:
    form = await request.form()
    form_data = {k: str(v) for k, v in form.items()}

    signature = request.headers.get("X-Twilio-Signature")
    if SETTINGS.twilio_validate_signature and not validate_twilio_signature(str(request.url), form_data, signature):
        logger.warning("twilio_signature_rejected url=%s", str(request.url))
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    reply_text = await run_in_threadpool(_process_inbound_sms, form_data)

    twiml = MessagingResponse()
    twiml.message(reply_text)
    return PlainTextResponse(content=str(twiml), media_type="application/xml")


@app.post("/dev/simulate-sms")
def dev_simulate_sms(payload: DevSimulateSmsPayload) -> dict[str, object]:
    form_data = {"From": payload.from_number, "Body": payload.body, "MessageSid": payload.message_sid}
    reply_text = _process_inbound_sms(form_data)
    return {"ok": True, "reply_text": reply_text, "message_sid": payload.message_sid}


def _process_inbound_sms(form_data: dict[str, str]) -> str:
    message_sid = form_data.get("MessageSid")
    from_number_raw = form_data.get("From", "")
    body = form_data.get("Body", "").strip()
    if not message_sid:
        raise HTTPException(status_code=400, detail="MessageSid is required")

    try:
        from_number = normalize_phone(from_number_raw)
    except InvalidPhoneNumber as exc:
        logger.warning("invalid_sender_number raw=%s", from_number_raw)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    queued_side_messages: list[tuple[UUID, UUID, str]] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            player_id = _get_or_create_player(cur, from_number)
            requested_session_code, cleaned_body = _extract_session_code(body)
            session_id, ambiguous = _resolve_active_session(cur, player_id, requested_session_code)

            inbound_id = _insert_inbound_message(
                cur,
                session_id=session_id,
                player_id=player_id,
                body=cleaned_body,
                provider_message_sid=message_sid,
            )

            if inbound_id is None:
                logger.info("duplicate_inbound_sid_ignored sid=%s", message_sid)
                return ""

            if ambiguous:
                reply_text = _format_ambiguous_session_reply(cur, player_id, requested_session_code)
            else:
                try:
                    context = build_context(cur, session_id, player_id)
                    result = process_inbound_message(cur, context, cleaned_body)
                    reply_text = result.reply_text
                    if result.should_broadcast and result.broadcast_text and session_id:
                        _queue_broadcast_message(
                            cur,
                            session_id,
                            body=result.broadcast_text,
                            queue=queued_side_messages,
                            exclude_player_id=player_id,
                        )
                    if result.direct_messages and session_id:
                        for target_player_id, text in result.direct_messages:
                            queued_side_messages.append((session_id, target_player_id, text))
                except Exception:
                    # Log internally but reply with a safe generic message so Twilio
                    # gets a 200 (not a 500 that would trigger retries, causing the
                    # inbound dedup guard to silently swallow the retry instead of
                    # actually re-processing).
                    logger.exception("inbound_sms_processing_error sid=%s", message_sid)
                    reply_text = "Sorry, something went wrong on our end. Please try again in a moment."

            insert_outbound_message(cur, session_id=session_id, player_id=player_id, body=reply_text)

    for queued_session_id, queued_player_id, body in queued_side_messages:
        _send_message_to_player(queued_session_id, queued_player_id, body)

    return reply_text


@app.get("/api/form-context")
def get_form_context(token: str = Query(..., min_length=20)) -> dict[str, object]:
    session_id, player_id = _parse_token_ids(token)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  s.id AS session_id,
                  s.target_date,
                  s.candidate_courses,
                  lead.name AS lead_name,
                  p.name AS player_name,
                  p.general_availability,
                  p.course_preferences,
                  p.standing_constraints
                FROM session_players sp
                JOIN sessions s ON s.id = sp.session_id
                JOIN players p ON p.id = sp.player_id
                LEFT JOIN players lead ON lead.id = s.lead_player_id
                WHERE sp.session_id = %s AND sp.player_id = %s
                LIMIT 1
                """,
                (session_id, player_id),
            )
            row = cur.fetchone()
            shared_courses = list_courses(cur, limit=50)

    if not row:
        raise HTTPException(status_code=404, detail="Session/player combination not found")

    general_availability = row["general_availability"] or []
    course_preferences = row["course_preferences"] or []
    standing_constraints = row["standing_constraints"]
    player_name = row["player_name"] or ""

    is_new_player = (
        player_name.startswith("Player ")
        and not general_availability
        and not course_preferences
        and not standing_constraints
    )

    return {
        "session_id": str(row["session_id"]),
        "player_id": str(player_id),
        "lead_name": row["lead_name"] or "Your lead",
        "target_date": row["target_date"].isoformat(),
        "candidate_courses": row["candidate_courses"] or [],
        "shared_courses": [course["name"] for course in shared_courses],
        "is_new_player": is_new_player,
        "agent_phone": SETTINGS.twilio_phone_number,
    }


@app.post(
    "/api/form-response",
    summary="Submit invitee form response using signed token",
    response_description="Persisted attendance and preference update result",
)
def submit_form_response(payload: FormResponsePayload) -> dict[str, object]:
    session_id, player_id = _parse_token_ids(payload.token)

    status = "confirmed" if payload.is_attending else "declined"

    queued_side_messages: list[tuple[UUID, UUID, str]] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.candidate_courses
                FROM session_players sp
                JOIN sessions s ON s.id = sp.session_id
                WHERE sp.session_id = %s AND sp.player_id = %s
                LIMIT 1
                """,
                (session_id, player_id),
            )
            membership = cur.fetchone()
            if not membership:
                raise HTTPException(status_code=404, detail="Session/player combination not found")

            approved_courses, available_time_blocks = _validated_form_preferences(
                is_attending=payload.is_attending,
                approved_courses=payload.approved_courses,
                available_time_blocks=payload.available_time_blocks,
                candidate_courses=[c for c in membership.get("candidate_courses") or [] if isinstance(c, str)],
            )

            cur.execute(
                """
                UPDATE session_players
                SET status = %s,
                    approved_courses = %s,
                    available_time_blocks = %s,
                    responded_at = now()
                WHERE session_id = %s AND player_id = %s
                RETURNING id
                """,
                (
                    status,
                    Jsonb(approved_courses),
                    Jsonb(available_time_blocks),
                    session_id,
                    player_id,
                ),
            )
            updated = cur.fetchone()

            if not updated:
                raise HTTPException(status_code=404, detail="Session/player combination not found")

            if payload.player_profile:
                _update_player_profile(cur, player_id, payload.player_profile)

            for course in approved_courses:
                upsert_course_snapshot(
                    cur,
                    name=course,
                    booking_url=None,
                    price_per_player=None,
                )

            session = get_session_state(cur, session_id)
            if session:
                policy = evaluate_session(session)
                proposals = ensure_session_proposals(cur, session, policy)
                if proposals:
                    lead_id = session["lead_player_id"]
                    lead_message = _format_proposal_summary_for_sms(proposals)
                    queued_side_messages.append((session_id, lead_id, lead_message))

    for queued_session_id, queued_player_id, body in queued_side_messages:
        _send_message_to_player(queued_session_id, queued_player_id, body)

    return {
        "ok": True,
        "session_id": str(session_id),
        "player_id": str(player_id),
        "status": status,
    }


def _parse_token_ids(token: str) -> tuple[UUID, UUID]:
    try:
        parsed = verify_form_token(token)
    except InvalidFormToken as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        session_id = UUID(str(parsed["session_id"]))
        player_id = UUID(str(parsed["player_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Token payload contains invalid IDs") from exc

    return session_id, player_id


def _update_player_profile(cur, player_id: UUID, profile: PlayerProfileUpdate) -> None:
    assignments: list[str] = []
    values: list[object] = []

    if profile.name and profile.name.strip():
        assignments.append("name = %s")
        values.append(profile.name.strip())

    assignments.append("general_availability = %s")
    values.append(Jsonb(profile.general_availability))

    assignments.append("course_preferences = %s")
    values.append(Jsonb(profile.course_preferences))

    assignments.append("standing_constraints = %s")
    values.append(profile.standing_constraints.strip() if profile.standing_constraints else None)

    assignments.append("updated_at = now()")

    values.append(player_id)
    query = f"UPDATE players SET {', '.join(assignments)} WHERE id = %s"
    cur.execute(query, tuple(values))


def _get_or_create_player(cur, phone: str, name: Optional[str] = None) -> UUID:
    cur.execute("SELECT id, name FROM players WHERE phone = %s", (phone,))
    row = cur.fetchone()
    if row:
        existing_name = row["name"] or ""
        if name and name.strip() and existing_name.startswith("Player "):
            cur.execute("UPDATE players SET name = %s WHERE id = %s", (name.strip(), row["id"]))
        return row["id"]

    player_name = name.strip() if name and name.strip() else f"Player {phone[-4:]}"
    cur.execute(
        """
        INSERT INTO players (name, phone)
        VALUES (%s, %s)
        RETURNING id
        """,
        (player_name, phone),
    )
    created = cur.fetchone()
    return created["id"]


def _resolve_active_session(cur, player_id: UUID, requested_session_code: str | None = None) -> tuple[UUID | None, bool]:
    cur.execute(
        """
        SELECT s.id, s.session_code
        FROM session_players sp
        JOIN sessions s ON s.id = sp.session_id
        WHERE sp.player_id = %s
          AND s.status = ANY(%s)
        ORDER BY s.created_at DESC
        LIMIT 25
        """,
        (player_id, list(ACTIVE_SESSION_STATUSES)),
    )
    rows = cur.fetchall()
    if requested_session_code:
        filtered = [row for row in rows if str(row.get("session_code") or "") == requested_session_code]
        if len(filtered) == 1:
            return filtered[0]["id"], False
        if len(rows) > 0:
            return None, True

    if len(rows) == 1:
        return rows[0]["id"], False
    if len(rows) > 1:
        hinted_session_id = _get_recent_active_session_hint(cur, player_id)
        if hinted_session_id and any(row["id"] == hinted_session_id for row in rows):
            return hinted_session_id, False
        return None, True
    return None, False


def _extract_session_code(body: str) -> tuple[str | None, str]:
    message = body.strip()
    prefix_match = _SESSION_CODE_PREFIX_RE.match(message)
    if prefix_match and prefix_match.group(1):
        return prefix_match.group(1), prefix_match.group(2).strip()

    inline_match = _SESSION_CODE_INLINE_RE.search(message)
    if inline_match:
        code = inline_match.group(1)
        cleaned = _SESSION_CODE_INLINE_RE.sub("", message).strip(" :,-")
        return code, cleaned or message
    return None, message


def _generate_session_code(cur) -> str:
    for _ in range(40):
        candidate = f"{random.randint(0, 9999):04d}"
        cur.execute(
            """
            SELECT 1
            FROM sessions
            WHERE session_code = %s
              AND status = ANY(%s)
            LIMIT 1
            """,
            (candidate, list(ACTIVE_SESSION_STATUSES)),
        )
        if not cur.fetchone():
            return candidate
    return f"{random.randint(0, 9999):04d}"


def _create_session_with_unique_code(
    cur,
    *,
    lead_player_id: UUID,
    target_date: date,
    candidate_courses: list[str],
) -> tuple[UUID, str]:
    for _ in range(_SESSION_CODE_INSERT_MAX_ATTEMPTS):
        session_code = _generate_session_code(cur)
        cur.execute("SAVEPOINT session_code_insert")
        try:
            cur.execute(
                """
                INSERT INTO sessions (lead_player_id, target_date, candidate_courses, session_code, status)
                VALUES (%s, %s, %s, %s, 'collecting')
                RETURNING id, session_code
                """,
                (lead_player_id, target_date, Jsonb(candidate_courses), session_code),
            )
            inserted = cur.fetchone()
            cur.execute("RELEASE SAVEPOINT session_code_insert")
            return inserted["id"], inserted["session_code"]
        except errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT session_code_insert")
            cur.execute("RELEASE SAVEPOINT session_code_insert")

    raise RuntimeError("Unable to allocate unique active session code after retries")


def _get_recent_active_session_hint(cur, player_id: UUID) -> UUID | None:
    cur.execute(
        """
        SELECT m.session_id
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE m.player_id = %s
          AND m.session_id IS NOT NULL
          AND s.status = ANY(%s)
        ORDER BY m.created_at DESC
        LIMIT 1
        """,
        (player_id, list(ACTIVE_SESSION_STATUSES)),
    )
    row = cur.fetchone()
    return row["session_id"] if row else None


def _list_active_sessions_for_player(cur, player_id: UUID) -> list[dict[str, object]]:
    cur.execute(
        """
        SELECT s.id, s.session_code, s.target_date, s.candidate_courses
        FROM session_players sp
        JOIN sessions s ON s.id = sp.session_id
        WHERE sp.player_id = %s
          AND s.status = ANY(%s)
        ORDER BY s.created_at DESC
        LIMIT 25
        """,
        (player_id, list(ACTIVE_SESSION_STATUSES)),
    )
    return cur.fetchall()


def _format_ambiguous_session_reply(cur, player_id: UUID, requested_session_code: str | None) -> str:
    sessions = _list_active_sessions_for_player(cur, player_id)
    if not sessions:
        return (
            "I couldn't find an active session for that code. "
            "Ask your lead to start a new round or send your form link."
        )

    lines = []
    if requested_session_code:
        lines.append(f"I couldn't match session code {requested_session_code}. Active sessions:")
    else:
        lines.append(
            "I see multiple active sessions. Reply with your 4-digit session code, "
            "for example: 0421: late morning works."
        )
        lines.append("You can also send just the code once (for example: 0421) to set the active session.")
    for row in sessions[:5]:
        code = str(row.get("session_code") or "----")
        date_text = row["target_date"].isoformat() if row.get("target_date") else "unknown-date"
        courses = [c for c in (row.get("candidate_courses") or []) if isinstance(c, str)]
        course_preview = ", ".join(courses[:2]) if courses else "no courses"
        lines.append(f"- {code}: {date_text} ({course_preview})")
    return "\n".join(lines)


def _insert_inbound_message(cur, session_id: UUID | None, player_id: UUID, body: str, provider_message_sid: str) -> UUID | None:
    cur.execute(
        """
        INSERT INTO messages (session_id, player_id, direction, body, provider_message_sid)
        VALUES (%s, %s, 'inbound', %s, %s)
        ON CONFLICT (provider_message_sid)
        WHERE direction = 'inbound' AND provider_message_sid IS NOT NULL
        DO NOTHING
        RETURNING id
        """,
        (session_id, player_id, body, provider_message_sid),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _format_proposal_summary_for_sms(proposals: list[dict[str, object]]) -> str:
    lines = ["Found options that fit everyone:"]
    for idx, item in enumerate(proposals, start=1):
        tee_time = item["tee_time"].strftime("%a %I:%M %p")
        price = float(item["price_per_player"]) if item["price_per_player"] is not None else 0
        lines.append(f"{idx}. {item['course']} {tee_time} (${price}/player)")
    lines.append("Reply with a number, then CONFIRM <number> to lock one in.")
    return "\n".join(lines)


def _send_message_to_player(session_id: UUID, player_id: UUID, body: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT phone FROM players WHERE id = %s", (player_id,))
            row = cur.fetchone()

    provider_sid = None
    if row and row.get("phone"):
        try:
            provider_sid = send_sms(str(row["phone"]), body)
        except Exception:  # pragma: no cover - provider/network errors
            logger.exception("Failed to send SMS to player_id=%s", player_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            insert_outbound_message(cur, session_id=session_id, player_id=player_id, body=body, provider_message_sid=provider_sid)


def _queue_broadcast_message(
    cur,
    session_id: UUID,
    body: str,
    queue: list[tuple[UUID, UUID, str]],
    exclude_player_id: UUID | None = None,
) -> None:
    players = list_session_players(cur, session_id)
    for player in players:
        player_id = player["player_id"]
        if exclude_player_id and player_id == exclude_player_id:
            continue
        queue.append((session_id, player_id, body))
