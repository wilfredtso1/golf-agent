from __future__ import annotations

import logging
from datetime import date
from typing import Optional
from uuid import UUID, uuid4
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field
from twilio.twiml.messaging_response import MessagingResponse

from agent import process_inbound_message
from config import SETTINGS
from context_builder import build_context
from db import get_conn
from policy_engine import evaluate_session
from token_utils import InvalidFormToken, generate_form_token, verify_form_token
from tools import (
    get_latest_proposals,
    list_courses,
    get_session_state,
    list_session_players,
    replace_tee_time_proposals,
    upsert_course_snapshot,
    update_session_status,
)
from twilio_helpers import InvalidPhoneNumber, normalize_phone, send_sms, validate_twilio_signature
from booking_provider import search_tee_times
from reminders import run_reminder_cycle

logger = logging.getLogger("golf-agent")
logging.basicConfig(level=logging.INFO)

ACTIVE_SESSION_STATUSES = ("collecting", "searching", "proposing")
DEFAULT_TIME_BLOCKS = ["early_morning", "late_morning", "early_afternoon"]

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
    token: str
    is_attending: bool
    approved_courses: list[str] = Field(default_factory=list)
    available_time_blocks: list[str] = Field(default_factory=list)
    player_profile: Optional[PlayerProfileUpdate] = None


class LeadInvitee(BaseModel):
    name: str
    phone: str


class LeadTriggerPayload(BaseModel):
    lead_phone: str
    lead_name: Optional[str] = None
    target_date: date
    candidate_courses: list[str] = Field(default_factory=list)
    invitees: list[LeadInvitee] = Field(default_factory=list)
    send_invites: bool = True


class DevSimulateSmsPayload(BaseModel):
    from_number: str
    body: str = ""
    message_sid: str = Field(default_factory=lambda: f"dev-{uuid4().hex}")


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


@app.get("/api/session-status")
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


@app.post("/api/lead-trigger")
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
            cur.execute(
                """
                INSERT INTO sessions (lead_player_id, target_date, candidate_courses, status)
                VALUES (%s, %s, %s, 'collecting')
                RETURNING id
                """,
                (lead_player_id, payload.target_date, Jsonb(cleaned_courses)),
            )
            session_id = cur.fetchone()["id"]

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
        with get_conn() as conn:
            with conn.cursor() as cur:
                for target in invite_targets:
                    token = generate_form_token(str(session_id), str(target["player_id"]))
                    form_link = _build_form_url(token)
                    message_body = (
                        f"Hey {target['name']}, this is Golf Agent helping "
                        f"{payload.lead_name or 'your lead'} coordinate a round on {payload.target_date.isoformat()}. "
                        f"Please submit your availability: {form_link}"
                    )
                    try:
                        provider_sid = send_sms(str(target["phone"]), message_body)
                        _insert_outbound_message(
                            cur,
                            session_id=session_id,
                            player_id=target["player_id"],
                            body=message_body,
                            provider_message_sid=provider_sid,
                        )
                        invite_results.append(
                            {"phone": str(target["phone"]), "status": "sent", "message_sid": provider_sid}
                        )
                    except Exception as exc:  # pragma: no cover - network/provider failures
                        logger.exception("Failed to send invite SMS to %s", target["phone"])
                        invite_results.append(
                            {"phone": str(target["phone"]), "status": "failed", "error": str(exc)}
                        )

    return {
        "ok": True,
        "session_id": str(session_id),
        "invite_count": len(invite_targets),
        "invites": invite_results,
    }


@app.post("/webhooks/twilio/sms")
async def twilio_sms_webhook(request: Request) -> Response:
    form = await request.form()
    form_data = {k: str(v) for k, v in form.items()}

    signature = request.headers.get("X-Twilio-Signature")
    if SETTINGS.twilio_validate_signature and not validate_twilio_signature(str(request.url), form_data, signature):
        logger.warning("Rejected Twilio webhook with invalid signature")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    reply_text = _process_inbound_sms(form_data)

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
        logger.warning("Invalid sender number: %s", from_number_raw)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with get_conn() as conn:
        with conn.cursor() as cur:
            player_id = _get_or_create_player(cur, from_number)
            session_id, ambiguous = _resolve_active_session(cur, player_id)

            inbound_id = _insert_inbound_message(
                cur,
                session_id=session_id,
                player_id=player_id,
                body=body,
                provider_message_sid=message_sid,
            )

            if inbound_id is None:
                logger.info("Duplicate inbound sid ignored: %s", message_sid)
                return ""

            if ambiguous:
                reply_text = (
                    "I see multiple active golf sessions for you. "
                    "Please tell me the course or date so I can route this message."
                )
            else:
                context = build_context(cur, session_id, player_id)
                result = process_inbound_message(cur, context, body)
                reply_text = result.reply_text
                if result.should_broadcast and result.broadcast_text and session_id:
                    _broadcast_message(cur, session_id, body=result.broadcast_text, exclude_player_id=player_id)
                if result.direct_messages and session_id:
                    for target_player_id, text in result.direct_messages:
                        _send_message_to_player(cur, session_id, target_player_id, text)

            _insert_outbound_message(cur, session_id=session_id, player_id=player_id, body=reply_text)

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


@app.post("/api/form-response")
def submit_form_response(payload: FormResponsePayload) -> dict[str, object]:
    session_id, player_id = _parse_token_ids(payload.token)

    if payload.is_attending:
        if not payload.approved_courses:
            raise HTTPException(status_code=400, detail="At least one approved course is required when attending")
        if not payload.available_time_blocks:
            raise HTTPException(status_code=400, detail="At least one available time block is required when attending")

    status = "confirmed" if payload.is_attending else "declined"
    approved_courses = payload.approved_courses if payload.is_attending else []
    available_time_blocks = payload.available_time_blocks if payload.is_attending else []

    with get_conn() as conn:
        with conn.cursor() as cur:
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
                if policy["minimum_group_size_met"] and policy["has_overlap"]:
                    options = search_tee_times(
                        target_date=session["target_date"],
                        time_windows=list(policy["time_overlap"]),
                        courses=list(policy["course_overlap"]),
                        group_size=int(policy["confirmed_count"]),
                    )
                    if options:
                        proposals = replace_tee_time_proposals(cur, session_id, options)
                        update_session_status(cur, session_id, "proposing")
                        lead_id = session["lead_player_id"]
                        lead_message = _format_proposal_summary_for_sms(proposals)
                        _send_message_to_player(cur, session_id, lead_id, lead_message)

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



def _build_form_url(token: str) -> str:
    query = urlencode({"token": token})
    return f"{SETTINGS.form_base_url}?{query}"


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



def _resolve_active_session(cur, player_id: UUID) -> tuple[UUID | None, bool]:
    cur.execute(
        """
        SELECT s.id
        FROM session_players sp
        JOIN sessions s ON s.id = sp.session_id
        WHERE sp.player_id = %s
          AND s.status = ANY(%s)
        ORDER BY s.created_at DESC
        """,
        (player_id, list(ACTIVE_SESSION_STATUSES)),
    )
    rows = cur.fetchall()

    if len(rows) == 1:
        return rows[0]["id"], False
    if len(rows) > 1:
        return None, True
    return None, False



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



def _insert_outbound_message(
    cur,
    session_id: UUID | None,
    player_id: UUID,
    body: str,
    provider_message_sid: Optional[str] = None,
) -> None:
    cur.execute(
        """
        INSERT INTO messages (session_id, player_id, direction, body, provider_message_sid)
        VALUES (%s, %s, 'outbound', %s, %s)
        """,
        (session_id, player_id, body, provider_message_sid),
    )


def _format_proposal_summary_for_sms(proposals: list[dict[str, object]]) -> str:
    lines = ["Found options that fit everyone:"]
    for idx, item in enumerate(proposals, start=1):
        tee_time = item["tee_time"].strftime("%a %I:%M %p")
        price = float(item["price_per_player"]) if item["price_per_player"] is not None else 0
        lines.append(f"{idx}. {item['course']} {tee_time} (${price}/player)")
    lines.append("Reply with a number, then CONFIRM <number> to lock one in.")
    return "\n".join(lines)


def _send_message_to_player(cur, session_id: UUID, player_id: UUID, body: str) -> None:
    cur.execute("SELECT phone FROM players WHERE id = %s", (player_id,))
    row = cur.fetchone()
    provider_sid = None
    if row and row.get("phone"):
        try:
            provider_sid = send_sms(str(row["phone"]), body)
        except Exception:  # pragma: no cover - provider/network errors
            logger.exception("Failed to send SMS to player_id=%s", player_id)
    _insert_outbound_message(cur, session_id=session_id, player_id=player_id, body=body, provider_message_sid=provider_sid)


def _broadcast_message(cur, session_id: UUID, body: str, exclude_player_id: UUID | None = None) -> None:
    players = list_session_players(cur, session_id)
    for player in players:
        player_id = player["player_id"]
        if exclude_player_id and player_id == exclude_player_id:
            continue
        _send_message_to_player(cur, session_id, player_id, body)
