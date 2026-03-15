from uuid import uuid4

from fastapi.testclient import TestClient

import main


class _Cur:
    def __init__(self, candidate_courses: list[str]):
        self._candidate_courses = candidate_courses
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql: str, params=None) -> None:
        if "SELECT s.candidate_courses" in sql:
            self._row = {"candidate_courses": self._candidate_courses}
            return
        raise AssertionError(f"Unexpected SQL in validation-only test: {sql}")

    def fetchone(self):
        return self._row


class _Conn:
    def __init__(self, candidate_courses: list[str]):
        self._candidate_courses = candidate_courses

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return _Cur(self._candidate_courses)


def test_form_response_rejects_invalid_time_block(monkeypatch) -> None:
    monkeypatch.setattr(main, "_parse_token_ids", lambda _token: (uuid4(), uuid4()))
    monkeypatch.setattr(main, "get_conn", lambda: _Conn(["Maple Moor", "Silver Lake"]))

    client = TestClient(main.app)
    resp = client.post(
        "/api/form-response",
        json={
            "token": "x" * 24,
            "is_attending": True,
            "approved_courses": ["Maple Moor"],
            "available_time_blocks": ["prime_time"],
        },
    )

    assert resp.status_code == 400
    assert "Invalid time blocks" in resp.json()["detail"]


def test_form_response_rejects_course_not_in_session_candidates(monkeypatch) -> None:
    monkeypatch.setattr(main, "_parse_token_ids", lambda _token: (uuid4(), uuid4()))
    monkeypatch.setattr(main, "get_conn", lambda: _Conn(["Maple Moor", "Silver Lake"]))

    client = TestClient(main.app)
    resp = client.post(
        "/api/form-response",
        json={
            "token": "x" * 24,
            "is_attending": True,
            "approved_courses": ["Bethpage"],
            "available_time_blocks": ["late_morning"],
        },
    )

    assert resp.status_code == 400
    assert "session candidates" in resp.json()["detail"]


def test_validated_form_preferences_normalize_courses_to_session_candidates() -> None:
    approved_courses, available_time_blocks = main._validated_form_preferences(
        is_attending=True,
        approved_courses=[" maple moor "],
        available_time_blocks=["late_morning"],
        candidate_courses=["Maple Moor", "Silver Lake"],
    )

    assert approved_courses == ["Maple Moor"]
    assert available_time_blocks == ["late_morning"]
