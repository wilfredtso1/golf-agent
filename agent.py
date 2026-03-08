from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

from config import SETTINGS
from llm import LLMError, parse_intent_with_llm
from booking_provider import search_tee_times
from policy_engine import evaluate_session
from token_utils import generate_form_token
from tools import (
    add_or_get_player_by_phone,
    add_player_to_session,
    get_latest_proposals,
    get_player_name,
    get_session_state,
    remove_player_from_session_by_name,
    replace_tee_time_proposals,
    select_proposal_by_position,
    update_session_courses,
    update_session_date,
    update_session_player,
    update_session_status,
)
from twilio_helpers import InvalidPhoneNumber, normalize_phone

_TIME_BLOCK_KEYWORDS = {
    "early_morning": ["early morning", "8-10", "8 to 10", "8am", "9am"],
    "late_morning": ["late morning", "10-12", "10 to 12", "10am", "11am"],
    "early_afternoon": ["early afternoon", "12-2", "12 to 2", "noon", "1pm"],
}

_DECLINE_KEYWORDS = [
    "i'm out",
    "im out",
    "can't make",
    "cant make",
    "not in",
    "decline",
    "out this time",
]

_ADD_PATTERN = re.compile(r"^add\s+(.+?)\s+(\+?[\d\s\-\(\)]{8,})$", re.IGNORECASE)
_REMOVE_PATTERN = re.compile(r"^remove\s+(.+)$", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"^(?:change|move|set)\s+date\s+(?:to\s+)?(\d{4}-\d{2}-\d{2})$", re.IGNORECASE)
_COURSE_PATTERN = re.compile(r"^(?:change|set|update)\s+courses?\s*[:\-]?\s*(.+)$", re.IGNORECASE)
_PROCEED_WITHOUT_PATTERN = re.compile(r"^proceed\s+without\s+them\b", re.IGNORECASE)


@dataclass
class AgentResult:
    reply_text: str
    should_broadcast: bool = False
    broadcast_text: Optional[str] = None
    direct_messages: list[tuple[UUID, str]] = field(default_factory=list)
    updated: bool = False
    debug: dict[str, object] = field(default_factory=dict)


def _build_form_url(token: str) -> str:
    return f"{SETTINGS.form_base_url}?{urlencode({'token': token})}"


def _parse_time_blocks(message_lower: str) -> list[str]:
    found: list[str] = []
    for slot, keywords in _TIME_BLOCK_KEYWORDS.items():
        if any(keyword in message_lower for keyword in keywords):
            found.append(slot)
    return found


def _parse_courses(message_lower: str, candidate_courses: list[str]) -> list[str]:
    selected: list[str] = []
    for course in candidate_courses:
        if course.lower() in message_lower:
            selected.append(course)
    return selected


def _extract_option_number(message: str) -> int | None:
    matched = re.search(r"\b(\d{1,2})\b", message)
    if not matched:
        return None
    return int(matched.group(1))


def _format_policy_summary(policy: dict[str, object]) -> str:
    confirmed_count = int(policy["confirmed_count"])
    if not policy["minimum_group_size_met"]:
        needed = max(0, 2 - confirmed_count)
        return f"We still need {needed} more confirmed player(s) before searching tee times."

    if not policy["course_overlap"] or not policy["time_overlap"]:
        return "I see a conflict in course/time overlap right now. I flagged this for the lead."

    courses = ", ".join(policy["course_overlap"])
    times = ", ".join(policy["time_overlap"])
    return f"Current overlap looks good. Shared courses: {courses}. Shared time windows: {times}."


def _format_proposals_message(proposals: list[dict[str, object]]) -> str:
    if not proposals:
        return "I couldn't find matching tee times yet."
    lines = ["Found options that fit current overlap:"]
    for i, p in enumerate(proposals, start=1):
        tee_time = p["tee_time"].strftime("%a %I:%M %p")
        lines.append(f"{i}. {p['course']} at {tee_time} (${p['price_per_player']}/player)")
    lines.append("Reply with an option number, then send CONFIRM <number> to lock it in.")
    return "\n".join(lines)


def _maybe_parse_intent_with_llm(context: dict[str, object], message: str) -> dict[str, object] | None:
    try:
        parsed = parse_intent_with_llm(context, message)
    except LLMError:
        return None
    if not parsed:
        return None
    return {
        "type": parsed.get("type", "none"),
        "available_time_blocks": [s for s in parsed.get("available_time_blocks", []) if isinstance(s, str)],
        "approved_courses": [c for c in parsed.get("approved_courses", []) if isinstance(c, str)],
        "option_number": parsed.get("option_number") if isinstance(parsed.get("option_number"), int) else None,
    }


def _ensure_proposals(cur, session: dict[str, object], policy: dict[str, object]) -> list[dict[str, object]]:
    if not (policy["minimum_group_size_met"] and policy["has_overlap"]):
        return []

    target_date = session.get("target_date")
    if target_date is None:
        return []
    group_size = int(policy["confirmed_count"])
    options = search_tee_times(
        target_date=target_date,
        time_windows=list(policy["time_overlap"]),
        courses=list(policy["course_overlap"]),
        group_size=group_size,
    )
    if not options:
        return []

    proposals = replace_tee_time_proposals(cur, session["id"], options)
    update_session_status(cur, session["id"], "proposing")
    return proposals


def process_inbound_message(cur, context: dict[str, object], inbound_body: str) -> AgentResult:
    message = inbound_body.strip()
    message_lower = message.lower()

    player = context["player"]
    player_name = player.get("name") or "there"
    is_lead = bool(player.get("is_lead"))
    session = context.get("session")

    if not session:
        return AgentResult(
            reply_text=(
                "I can help coordinate golf tee times. If you were invited to a round, "
                "please use your form link or ask your lead to start a session."
            )
        )

    session_id = session["id"]
    player_id = player["id"]
    lead_id = session["lead_player_id"]
    candidate_courses = [c for c in session.get("candidate_courses") or [] if isinstance(c, str)]

    # Deterministic confirmation gate for final tee-time commitment.
    confirm_match = re.match(r"^confirm\s+(\d{1,2})\b", message_lower)
    if confirm_match:
        if not is_lead:
            return AgentResult(reply_text="Only the lead can confirm a tee-time option.")
        option_number = int(confirm_match.group(1))
        selected = select_proposal_by_position(cur, session_id, option_number)
        if not selected:
            return AgentResult(reply_text="I couldn't match that option number. Please pick a valid proposal number.")

        update_session_status(cur, session_id, "confirmed")
        lock_msg = (
            f"Locked in: {selected['course']}, {selected['tee_time'].strftime('%A %I:%M %p')}. "
            f"{player_name} is booking now."
        )
        lead_reply = f"Confirmed option {option_number}. Book here for the group: {selected['booking_url']}"
        return AgentResult(
            reply_text=lead_reply,
            should_broadcast=True,
            broadcast_text=lock_msg,
            updated=True,
        )

    if is_lead:
        proceed_match = _PROCEED_WITHOUT_PATTERN.match(message)
        if proceed_match:
            players = [p for p in session.get("players", []) if isinstance(p, dict)]
            has_unresponsive = any((p.get("status") or "").lower() == "unresponsive" for p in players)
            if not has_unresponsive:
                return AgentResult(reply_text="There are no unresponsive players in this session right now.")

            policy = evaluate_session(session)
            if not policy["minimum_group_size_met"]:
                needed = max(0, 2 - int(policy["confirmed_count"]))
                return AgentResult(
                    reply_text=f"I still need {needed} more confirmed player(s) before I can proceed."
                )
            if not policy["has_overlap"]:
                return AgentResult(reply_text="I still see a course/time overlap conflict and can't proceed yet.")

            proposals = _ensure_proposals(cur, session, policy)
            if not proposals:
                return AgentResult(reply_text="Proceeding without unresponsive players, but I couldn't find matching tee times yet.")

            return AgentResult(
                reply_text=(
                    "Proceeding without unresponsive players.\n"
                    f"{_format_proposals_message(proposals)}"
                ),
                updated=True,
            )

        add_match = _ADD_PATTERN.match(message)
        if add_match:
            raw_name, raw_phone = add_match.groups()
            try:
                phone = normalize_phone(raw_phone)
            except InvalidPhoneNumber:
                return AgentResult(reply_text="That phone number looks invalid. Please include a valid mobile number.")
            name = " ".join(raw_name.split()).strip()
            if not name:
                return AgentResult(reply_text="Please include the new player's name.")
            new_player_id = add_or_get_player_by_phone(cur, phone=phone, name=name)
            inserted = add_player_to_session(cur, session_id=session_id, player_id=new_player_id)
            update_session_status(cur, session_id, "collecting")
            form_token = generate_form_token(str(session_id), str(new_player_id))
            form_link = _build_form_url(form_token)
            invite_message = (
                f"Hey {name}, this is Golf Agent helping {player_name} coordinate a round on "
                f"{session['target_date'].isoformat()}. Please submit your availability: {form_link}"
            )
            reply = "Player added and invited." if inserted else "Player already in this session; invite re-sent."
            return AgentResult(
                reply_text=reply,
                should_broadcast=True,
                broadcast_text=f"Lead update: {name} was added to this session.",
                direct_messages=[(new_player_id, invite_message)],
                updated=True,
            )

        remove_match = _REMOVE_PATTERN.match(message)
        if remove_match:
            name = " ".join(remove_match.group(1).split()).strip()
            if not name:
                return AgentResult(reply_text="Please include the player name to remove.")
            lead_name = get_player_name(cur, lead_id)
            if name.lower() == lead_name.lower():
                return AgentResult(reply_text="Lead cannot be removed from their own session.")
            removed = remove_player_from_session_by_name(cur, session_id=session_id, name=name)
            if not removed:
                return AgentResult(reply_text=f"I couldn't find {name} in this session.")
            update_session_status(cur, session_id, "collecting")
            return AgentResult(
                reply_text=f"Removed {name} from the session.",
                should_broadcast=True,
                broadcast_text=f"Lead update: {name} was removed from this session.",
                updated=True,
            )

        date_match = _DATE_PATTERN.match(message)
        if date_match:
            raw_date = date_match.group(1)
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError:
                return AgentResult(reply_text="That date format looks invalid. Use YYYY-MM-DD.")
            update_session_date(cur, session_id=session_id, target_date=parsed_date)
            return AgentResult(
                reply_text=f"Session date moved to {parsed_date.isoformat()} and players were re-polled.",
                should_broadcast=True,
                broadcast_text=f"Heads up: the round date moved to {parsed_date.isoformat()}. Please re-submit availability.",
                updated=True,
            )

        course_match = _COURSE_PATTERN.match(message)
        if course_match:
            courses = [c.strip() for c in course_match.group(1).split(",") if c.strip()]
            if not courses:
                return AgentResult(reply_text="Please provide at least one course when updating courses.")
            update_session_courses(cur, session_id=session_id, candidate_courses=courses)
            return AgentResult(
                reply_text="Candidate courses updated and players were re-polled.",
                should_broadcast=True,
                broadcast_text=f"Heads up: candidate courses were updated to {', '.join(courses)}. Please re-submit availability.",
                updated=True,
            )

    # Lead can stage an option pick, but must explicitly CONFIRM to execute it.
    if is_lead:
        proposed_option = _extract_option_number(message)
        if proposed_option is not None:
            proposals = get_latest_proposals(cur, session_id)
            if proposals and 1 <= proposed_option <= len(proposals):
                return AgentResult(
                    reply_text=(
                        f"Got it. To finalize option {proposed_option}, reply exactly: "
                        f"CONFIRM {proposed_option}"
                    )
                )

    selected_times = _parse_time_blocks(message_lower)
    selected_courses = _parse_courses(message_lower, candidate_courses)
    parsed_decline = any(keyword in message_lower for keyword in _DECLINE_KEYWORDS)

    llm_intent = None
    if not (selected_times or selected_courses or parsed_decline):
        llm_intent = _maybe_parse_intent_with_llm(context, message)
        if llm_intent:
            if llm_intent["type"] == "decline":
                parsed_decline = True
            elif llm_intent["type"] == "preferences":
                if not selected_times:
                    selected_times = list(llm_intent["available_time_blocks"])
                if not selected_courses:
                    selected_courses = [c for c in llm_intent["approved_courses"] if c in candidate_courses]

    if parsed_decline:
        update_session_player(
            cur,
            session_id,
            player_id,
            status="declined",
            approved_courses=[],
            available_time_blocks=[],
        )

        refreshed = get_session_state(cur, session_id)
        policy = evaluate_session(refreshed or session)
        summary = _format_policy_summary(policy)

        lead_msg = f"Update: {player_name} is out for this session. {summary}"
        direct = []
        if lead_id != player_id:
            direct.append((lead_id, lead_msg))

        return AgentResult(
            reply_text=(
                f"Understood, {player_name}. I marked you as out for this session and updated the lead."
            ),
            should_broadcast=True,
            broadcast_text=f"Update: {player_name} is out for this session.",
            direct_messages=direct,
            updated=True,
            debug={"policy": policy},
        )

    if selected_times or selected_courses:
        update_session_player(
            cur,
            session_id,
            player_id,
            status="confirmed",
            available_time_blocks=selected_times or None,
            approved_courses=selected_courses or None,
        )

        refreshed = get_session_state(cur, session_id)
        current_session = refreshed or session
        policy = evaluate_session(current_session)

        proposals = _ensure_proposals(cur, current_session, policy)
        direct: list[tuple[UUID, str]] = []
        if proposals:
            direct.append((lead_id, _format_proposals_message(proposals)))

        summary = _format_policy_summary(policy)
        return AgentResult(
            reply_text=f"Thanks {player_name}, I updated your preferences. {summary}",
            direct_messages=direct,
            updated=True,
            debug={"policy": policy, "llm_intent": llm_intent or {}},
        )

    policy = evaluate_session(session)
    return AgentResult(reply_text=_format_policy_summary(policy), debug={"policy": policy})
