from datetime import date
from uuid import uuid4

import agent


def _context() -> dict[str, object]:
    session_id = uuid4()
    player_id = uuid4()
    return {
        "session": {
            "id": session_id,
            "lead_player_id": uuid4(),
            "target_date": date(2026, 3, 20),
            "candidate_courses": ["Bethpage", "Marine Park"],
            "players": [
                {
                    "player_id": player_id,
                    "name": "Dave",
                    "status": "invited",
                    "approved_courses": [],
                    "available_time_blocks": [],
                },
                {
                    "player_id": uuid4(),
                    "name": "Lead",
                    "status": "confirmed",
                    "approved_courses": ["Bethpage", "Marine Park"],
                    "available_time_blocks": ["early_morning", "late_morning"],
                },
            ],
        },
        "player": {
            "id": player_id,
            "name": "Dave",
            "is_lead": False,
            "session_state": None,
            "profile": {},
        },
        "recent_messages": [],
    }


def test_process_inbound_updates_preferences(monkeypatch) -> None:
    calls = {"update_session_player": 0, "update_session_status": 0}

    def fake_update_session_player(*args, **kwargs):
        calls["update_session_player"] += 1

    def fake_get_session_state(*args, **kwargs):
        ctx = _context()
        ctx["session"]["players"][0]["status"] = "confirmed"
        ctx["session"]["players"][0]["approved_courses"] = ["Bethpage"]
        ctx["session"]["players"][0]["available_time_blocks"] = ["late_morning"]
        return ctx["session"]

    def fake_update_session_status(*args, **kwargs):
        calls["update_session_status"] += 1

    monkeypatch.setattr(agent, "update_session_player", fake_update_session_player)
    monkeypatch.setattr(agent, "get_session_state", fake_get_session_state)
    monkeypatch.setattr(agent, "update_session_status", fake_update_session_status)
    monkeypatch.setattr(agent, "replace_tee_time_proposals", lambda *args, **kwargs: [])

    result = agent.process_inbound_message(None, _context(), "late morning at bethpage works")

    assert "updated your preferences" in result.reply_text.lower()
    assert calls["update_session_player"] == 1


def test_process_inbound_decline(monkeypatch) -> None:
    calls = {"update_session_player": 0}

    def fake_update_session_player(*args, **kwargs):
        calls["update_session_player"] += 1

    def fake_get_session_state(*args, **kwargs):
        return _context()["session"]

    monkeypatch.setattr(agent, "update_session_player", fake_update_session_player)
    monkeypatch.setattr(agent, "get_session_state", fake_get_session_state)

    result = agent.process_inbound_message(None, _context(), "I'm out this time")

    assert "marked you as out" in result.reply_text.lower()
    assert result.should_broadcast is True
    assert calls["update_session_player"] == 1
