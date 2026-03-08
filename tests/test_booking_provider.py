from datetime import date
from types import SimpleNamespace

import booking_provider


def test_booking_provider_uses_mock_by_default(monkeypatch) -> None:
    monkeypatch.setattr(booking_provider, "SETTINGS", SimpleNamespace(tee_time_provider="mock"))
    monkeypatch.setattr(
        booking_provider,
        "search_mock_tee_times",
        lambda **kwargs: [{"provider": "mock", "course": "Maple Moor"}],
    )
    monkeypatch.setattr(
        booking_provider,
        "search_golfnow_tee_times",
        lambda **kwargs: [{"provider": "golfnow", "course": "Maple Moor"}],
    )

    rows = booking_provider.search_tee_times(
        target_date=date(2026, 3, 15),
        time_windows=["late_morning"],
        courses=["Maple Moor"],
        group_size=2,
    )
    assert rows[0]["provider"] == "mock"


def test_booking_provider_uses_golfnow_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(booking_provider, "SETTINGS", SimpleNamespace(tee_time_provider="golfnow"))
    monkeypatch.setattr(
        booking_provider,
        "search_mock_tee_times",
        lambda **kwargs: [{"provider": "mock", "course": "Maple Moor"}],
    )
    monkeypatch.setattr(
        booking_provider,
        "search_golfnow_tee_times",
        lambda **kwargs: [{"provider": "golfnow", "course": "Maple Moor"}],
    )

    rows = booking_provider.search_tee_times(
        target_date=date(2026, 3, 15),
        time_windows=["late_morning"],
        courses=["Maple Moor"],
        group_size=2,
    )
    assert rows[0]["provider"] == "golfnow"


def test_booking_provider_falls_back_to_mock_when_golfnow_empty(monkeypatch) -> None:
    monkeypatch.setattr(booking_provider, "SETTINGS", SimpleNamespace(tee_time_provider="golfnow"))
    monkeypatch.setattr(booking_provider, "search_golfnow_tee_times", lambda **kwargs: [])
    monkeypatch.setattr(
        booking_provider,
        "search_mock_tee_times",
        lambda **kwargs: [{"provider": "mock", "course": "Maple Moor"}],
    )

    rows = booking_provider.search_tee_times(
        target_date=date(2026, 3, 15),
        time_windows=["late_morning"],
        courses=["Maple Moor"],
        group_size=2,
    )
    assert rows[0]["provider"] == "mock"


def test_booking_provider_falls_back_to_mock_when_golfnow_errors(monkeypatch) -> None:
    monkeypatch.setattr(booking_provider, "SETTINGS", SimpleNamespace(tee_time_provider="golfnow"))

    def _boom(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(booking_provider, "search_golfnow_tee_times", _boom)
    monkeypatch.setattr(
        booking_provider,
        "search_mock_tee_times",
        lambda **kwargs: [{"provider": "mock", "course": "Maple Moor"}],
    )

    rows = booking_provider.search_tee_times(
        target_date=date(2026, 3, 15),
        time_windows=["late_morning"],
        courses=["Maple Moor"],
        group_size=2,
    )
    assert rows[0]["provider"] == "mock"
