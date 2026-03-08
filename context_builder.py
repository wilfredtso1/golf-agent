from __future__ import annotations

from uuid import UUID

from tools import get_player_profile, get_player_session_state, get_recent_messages, get_session_state


def build_context(cur, session_id: UUID | None, player_id: UUID, recent_limit: int = 10) -> dict[str, object]:
    player_profile = get_player_profile(cur, player_id)
    if not player_profile:
        raise RuntimeError(f"Player not found for id: {player_id}")

    session = get_session_state(cur, session_id) if session_id else None
    player_session_state = get_player_session_state(cur, session_id, player_id) if session_id else None
    is_lead = bool(session and session.get("lead_player_id") == player_id)

    return {
        "session": session,
        "player": {
            "id": player_id,
            "name": player_profile["name"],
            "phone": player_profile["phone"],
            "is_lead": is_lead,
            "session_state": player_session_state,
            "profile": player_profile,
        },
        "recent_messages": get_recent_messages(cur, session_id, player_id, limit=recent_limit),
    }
