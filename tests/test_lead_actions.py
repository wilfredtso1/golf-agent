from datetime import date
from uuid import uuid4

import agent


def _context(*, is_lead: bool = True) -> dict[str, object]:
    lead_id = uuid4()
    player_id = lead_id if is_lead else uuid4()
    return {
        "session": {
            "id": uuid4(),
            "lead_player_id": lead_id,
            "target_date": date(2026, 3, 22),
            "candidate_courses": ["Bethpage", "Marine Park"],
            "players": [],
        },
        "player": {
            "id": player_id,
            "name": "Will" if is_lead else "Dave",
            "is_lead": is_lead,
            "session_state": None,
            "profile": {},
        },
        "recent_messages": [],
    }


def test_lead_add_player_executes_immediately(monkeypatch) -> None:
    new_player_id = uuid4()
    monkeypatch.setattr(agent, "add_or_get_player_by_phone", lambda *args, **kwargs: new_player_id)
    monkeypatch.setattr(agent, "add_player_to_session", lambda *args, **kwargs: True)
    monkeypatch.setattr(agent, "generate_form_token", lambda *args, **kwargs: "tok123")
    monkeypatch.setattr(agent, "update_session_status", lambda *args, **kwargs: None)
    result = agent.process_inbound_message(None, _context(is_lead=True), "add Tom +19175550123")

    assert "player added" in result.reply_text.lower()
    assert len(result.direct_messages) == 1
    assert result.direct_messages[0][0] == new_player_id


def test_lead_changes_date_executes_immediately(monkeypatch) -> None:
    calls = {"date": 0}

    def fake_update_session_date(*args, **kwargs):
        calls["date"] += 1

    monkeypatch.setattr(agent, "update_session_date", fake_update_session_date)

    result = agent.process_inbound_message(None, _context(is_lead=True), "change date to 2026-04-01")

    assert calls["date"] == 1
    assert result.should_broadcast is True
    assert "moved to 2026-04-01" in result.reply_text.lower()


def test_proceed_without_them_generates_proposals(monkeypatch) -> None:
    ctx = _context(is_lead=True)
    ctx["session"]["players"] = [
        {
            "player_id": ctx["session"]["lead_player_id"],
            "name": "Will",
            "status": "confirmed",
            "approved_courses": ["Bethpage"],
            "available_time_blocks": ["late_morning"],
        },
        {
            "player_id": uuid4(),
            "name": "Jane",
            "status": "confirmed",
            "approved_courses": ["Bethpage"],
            "available_time_blocks": ["late_morning"],
        },
        {
            "player_id": uuid4(),
            "name": "Dave",
            "status": "unresponsive",
            "approved_courses": [],
            "available_time_blocks": [],
        },
    ]

    monkeypatch.setattr(
        agent,
        "_ensure_proposals",
        lambda *args, **kwargs: [
            {
                "course": "Bethpage",
                "tee_time": date(2026, 3, 22),
                "price_per_player": 42,
            }
        ],
    )

    result = agent.process_inbound_message(None, ctx, "PROCEED WITHOUT THEM")

    assert "proceeding without unresponsive players" in result.reply_text.lower()
    assert "found options" in result.reply_text.lower()
