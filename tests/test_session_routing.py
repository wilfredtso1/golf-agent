from datetime import date
from uuid import uuid4

from psycopg import errors

import main


def test_extract_session_code_from_prefix() -> None:
    code, cleaned = main._extract_session_code("0421: late morning works")
    assert code == "0421"
    assert cleaned == "late morning works"


def test_extract_session_code_from_inline() -> None:
    code, cleaned = main._extract_session_code("for 77 late morning works")
    assert code == "77"
    assert "77" not in cleaned


def test_extract_session_code_no_code() -> None:
    code, cleaned = main._extract_session_code("late morning works")
    assert code is None
    assert cleaned == "late morning works"


def test_extract_session_code_code_only() -> None:
    code, cleaned = main._extract_session_code("0421")
    assert code == "0421"
    assert cleaned == ""


class _StubCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return None

    def fetchall(self):
        return self._rows


class _InsertRetryCursor:
    def __init__(self, fail_attempts: int = 0):
        self.fail_attempts = fail_attempts
        self.insert_calls = 0
        self._row = None

    def execute(self, query, params=None):
        compact = " ".join(str(query).split())
        if compact.startswith("INSERT INTO sessions"):
            self.insert_calls += 1
            if self.insert_calls <= self.fail_attempts:
                raise errors.UniqueViolation("duplicate session_code")
            self._row = {"id": uuid4(), "session_code": params[3]}
        return None

    def fetchone(self):
        return self._row


def test_resolve_active_session_uses_recent_hint(monkeypatch) -> None:
    first = {"id": uuid4(), "session_code": "0421"}
    second = {"id": uuid4(), "session_code": "0099"}
    cur = _StubCursor([first, second])

    monkeypatch.setattr(main, "_get_recent_active_session_hint", lambda *_: second["id"])
    session_id, ambiguous = main._resolve_active_session(cur, uuid4(), None)
    assert ambiguous is False
    assert session_id == second["id"]


def test_create_session_with_unique_code_retries_on_duplicate(monkeypatch) -> None:
    codes = iter(["0001", "0002"])
    monkeypatch.setattr(main, "_generate_session_code", lambda *_: next(codes))
    cur = _InsertRetryCursor(fail_attempts=1)

    _, session_code = main._create_session_with_unique_code(
        cur,
        lead_player_id=uuid4(),
        target_date=date(2026, 3, 15),
        candidate_courses=["Maple Moor"],
    )
    assert cur.insert_calls == 2
    assert session_code == "0002"


def test_create_session_with_unique_code_raises_after_retries(monkeypatch) -> None:
    monkeypatch.setattr(main, "_generate_session_code", lambda *_: "0001")
    cur = _InsertRetryCursor(fail_attempts=main._SESSION_CODE_INSERT_MAX_ATTEMPTS)

    try:
        main._create_session_with_unique_code(
            cur,
            lead_player_id=uuid4(),
            target_date=date(2026, 3, 15),
            candidate_courses=["Maple Moor"],
        )
        raised = False
    except RuntimeError:
        raised = True
    assert raised is True


def test_format_ambiguous_session_reply_includes_active_codes(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "_list_active_sessions_for_player",
        lambda *_: [
            {"session_code": "0421", "target_date": date(2026, 3, 15), "candidate_courses": ["Maple Moor", "Dyker"]},
            {"session_code": "0099", "target_date": date(2026, 3, 16), "candidate_courses": ["Saxon Woods"]},
        ],
    )
    reply = main._format_ambiguous_session_reply(None, uuid4(), None)
    assert "0421" in reply
    assert "0099" in reply
    assert "multiple active sessions" in reply.lower()
