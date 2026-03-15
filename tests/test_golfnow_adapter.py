from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import golfnow_adapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_element(text: str = "", href: str = "") -> MagicMock:
    el = MagicMock()
    el.inner_text.return_value = text
    el.get_attribute.return_value = href
    return el


def make_mock_card(time_str: str, price_str: str, href: str) -> MagicMock:
    card = MagicMock()

    def _query_selector(sel: str) -> MagicMock:
        # Check price before time: ".tee-time-price" contains "time" as a substring
        if "price" in sel:
            return _make_element(price_str)
        if "time" in sel:
            return _make_element(time_str)
        if "a[href" in sel:
            return _make_element(href=href)
        return _make_element()

    card.query_selector.side_effect = _query_selector
    return card


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc)


def _make_settings(**overrides) -> SimpleNamespace:
    defaults = dict(
        default_timezone="America/New_York",
        golfnow_scrape_timeout_ms=20000,
        golfnow_scrape_headless=True,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# 1. Returns empty when courses list is empty
# ---------------------------------------------------------------------------


def test_returns_empty_when_no_courses_resolve(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())
    monkeypatch.setattr(
        golfnow_adapter, "list_courses", lambda cur, limit: [{"name": "Dyker Beach"}]
    )

    launched = []

    def _fake_scrape(*args, **kwargs):
        launched.append(args)
        return []

    with patch.object(golfnow_adapter, "_scrape_one_course", side_effect=_fake_scrape):
        with _fake_db_conn(monkeypatch):
            result = golfnow_adapter.search_tee_times(
                target_date=date(2026, 3, 22),
                time_windows=["early_morning"],
                courses=[],  # empty input → nothing to search
                group_size=2,
            )

    assert result == []
    assert launched == []  # no browser launched


# ---------------------------------------------------------------------------
# 1b. Hybrid: unrecognized course passes raw name to GolfNow
# ---------------------------------------------------------------------------


def test_hybrid_uses_raw_name_when_no_db_match(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())
    monkeypatch.setattr(
        golfnow_adapter, "list_courses", lambda cur, limit: []  # empty catalog
    )
    monkeypatch.setattr(golfnow_adapter, "upsert_course_snapshot", MagicMock())

    scraped_with = []

    def _fake_scrape(course, target_date, time_windows, group_size):
        scraped_with.append(course)
        return []

    with patch.object(golfnow_adapter, "_scrape_one_course", side_effect=_fake_scrape):
        with _fake_db_conn(monkeypatch):
            golfnow_adapter.search_tee_times(
                target_date=date(2026, 3, 22),
                time_windows=["early_morning"],
                courses=["Unknown Course XYZ"],
                group_size=2,
            )

    assert scraped_with == ["Unknown Course XYZ"]


# ---------------------------------------------------------------------------
# 2. Filters by time window
# ---------------------------------------------------------------------------


def test_filters_by_time_window(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())

    # 9 AM card (early_morning) and 2 PM card (early_afternoon)
    card_9am = make_mock_card("9:00 AM", "$45", "/tee-times/abc")
    card_2pm = make_mock_card("2:00 PM", "$55", "/tee-times/def")

    result = golfnow_adapter._parse_card(card_9am, "Dyker Beach", date(2026, 3, 22), ["early_morning"])
    assert result is not None
    assert result["course"] == "Dyker Beach"

    result_filtered = golfnow_adapter._parse_card(card_2pm, "Dyker Beach", date(2026, 3, 22), ["early_morning"])
    assert result_filtered is None


# ---------------------------------------------------------------------------
# 3. UTC conversion
# ---------------------------------------------------------------------------


def test_utc_conversion(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings(default_timezone="America/New_York"))

    card = make_mock_card("9:00 AM", "$45", "/tee-times/abc")
    result = golfnow_adapter._parse_card(card, "Dyker Beach", date(2026, 3, 22), ["early_morning"])

    assert result is not None
    tee_time: datetime = result["tee_time"]
    assert tee_time.tzinfo == timezone.utc
    # 9 AM ET on 2026-03-22 (EDT = UTC-4) → 13:00 UTC
    assert tee_time.hour == 13
    assert tee_time.minute == 0


# ---------------------------------------------------------------------------
# 4. max_results capped
# ---------------------------------------------------------------------------


def test_max_results_capped(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())
    monkeypatch.setattr(golfnow_adapter, "resolve_course_candidates", lambda c, cats: c)
    monkeypatch.setattr(
        golfnow_adapter, "list_courses", lambda cur, limit: [{"name": "Dyker Beach"}]
    )

    cards = [make_mock_card(f"{8 + i}:00 AM", f"${40 + i}", f"/tee-times/{i}") for i in range(5)]

    def _fake_scrape(course, target_date, time_windows, group_size):
        results = []
        for card in cards:
            r = golfnow_adapter._parse_card(card, course, target_date, time_windows)
            if r:
                results.append(r)
        return results

    with patch.object(golfnow_adapter, "_scrape_one_course", side_effect=_fake_scrape):
        with _fake_db_conn(monkeypatch):
            result = golfnow_adapter.search_tee_times(
                target_date=date(2026, 3, 22),
                time_windows=["early_morning"],
                courses=["Dyker Beach"],
                group_size=2,
                max_results=2,
            )

    assert len(result) == 2


# ---------------------------------------------------------------------------
# 5. Scrape failure returns empty (not exception)
# ---------------------------------------------------------------------------


def test_scrape_failure_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())
    monkeypatch.setattr(golfnow_adapter, "resolve_course_candidates", lambda c, cats: c)
    monkeypatch.setattr(
        golfnow_adapter, "list_courses", lambda cur, limit: [{"name": "Dyker Beach"}]
    )

    def _boom(course, target_date, time_windows, group_size):
        raise RuntimeError("Playwright timeout")

    with patch.object(golfnow_adapter, "_scrape_one_course", side_effect=_boom):
        with _fake_db_conn(monkeypatch):
            result = golfnow_adapter.search_tee_times(
                target_date=date(2026, 3, 22),
                time_windows=["early_morning"],
                courses=["Dyker Beach"],
                group_size=2,
            )

    assert result == []


# ---------------------------------------------------------------------------
# 6. Non-parseable price → price_per_player=0.0, result still included
# ---------------------------------------------------------------------------


def test_price_parse_fallback(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())

    card = make_mock_card("9:00 AM", "N/A", "/tee-times/abc")
    result = golfnow_adapter._parse_card(card, "Dyker Beach", date(2026, 3, 22), ["early_morning"])

    assert result is not None
    assert result["price_per_player"] == 0.0


# ---------------------------------------------------------------------------
# 7. Multiple courses, partial failure → partial results
# ---------------------------------------------------------------------------


def test_multiple_courses_partial_failure(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())
    monkeypatch.setattr(golfnow_adapter, "resolve_course_candidates", lambda c, cats: c)
    monkeypatch.setattr(
        golfnow_adapter,
        "list_courses",
        lambda cur, limit: [{"name": "Dyker Beach"}, {"name": "Bethpage Black"}],
    )

    good_card = make_mock_card("9:00 AM", "$45", "/tee-times/abc")

    def _fake_scrape(course, target_date, time_windows, group_size):
        if course == "Bethpage Black":
            raise RuntimeError("blocked")
        return [golfnow_adapter._parse_card(good_card, course, target_date, time_windows)]

    with patch.object(golfnow_adapter, "_scrape_one_course", side_effect=_fake_scrape):
        with _fake_db_conn(monkeypatch):
            result = golfnow_adapter.search_tee_times(
                target_date=date(2026, 3, 22),
                time_windows=["early_morning"],
                courses=["Dyker Beach", "Bethpage Black"],
                group_size=2,
                max_results=10,
            )

    assert len(result) == 1
    assert result[0]["course"] == "Dyker Beach"


# ---------------------------------------------------------------------------
# 8. Sort order: by tee_time then price_per_player
# ---------------------------------------------------------------------------


def test_sorted_by_tee_time_then_price(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())

    # Three cards: 10 AM $60, 9 AM $50, 9 AM $40
    card_10am_60 = make_mock_card("10:00 AM", "$60", "/tee-times/c")
    card_9am_50 = make_mock_card("9:00 AM", "$50", "/tee-times/b")
    card_9am_40 = make_mock_card("9:00 AM", "$40", "/tee-times/a")

    target = date(2026, 3, 22)
    windows = ["early_morning", "late_morning"]

    results = [
        golfnow_adapter._parse_card(card_10am_60, "CourseA", target, windows),
        golfnow_adapter._parse_card(card_9am_50, "CourseA", target, windows),
        golfnow_adapter._parse_card(card_9am_40, "CourseA", target, windows),
    ]
    results = [r for r in results if r is not None]
    results.sort(key=lambda item: (item["tee_time"], item["price_per_player"]))

    prices = [r["price_per_player"] for r in results]
    assert prices == [40.0, 50.0, 60.0]
    assert results[0]["tee_time"] < results[2]["tee_time"]


# ---------------------------------------------------------------------------
# 9. Hybrid: newly-discovered course is upserted into the DB
# ---------------------------------------------------------------------------


def test_new_course_upserted_after_scrape(monkeypatch) -> None:
    monkeypatch.setattr(golfnow_adapter, "SETTINGS", _make_settings())
    monkeypatch.setattr(
        golfnow_adapter, "list_courses", lambda cur, limit: []  # empty catalog
    )
    mock_upsert = MagicMock()
    monkeypatch.setattr(golfnow_adapter, "upsert_course_snapshot", mock_upsert)

    good_card = make_mock_card("9:00 AM", "$45", "/tee-times/abc")

    def _fake_scrape(course, target_date, time_windows, group_size):
        return [golfnow_adapter._parse_card(good_card, course, target_date, time_windows)]

    with patch.object(golfnow_adapter, "_scrape_one_course", side_effect=_fake_scrape):
        with _fake_db_conn(monkeypatch):
            result = golfnow_adapter.search_tee_times(
                target_date=date(2026, 3, 22),
                time_windows=["early_morning"],
                courses=["Brand New Course"],
                group_size=2,
            )

    assert len(result) == 1
    mock_upsert.assert_called_once()
    call_kwargs = mock_upsert.call_args.kwargs
    assert call_kwargs["name"] == "Brand New Course"
    assert call_kwargs["price_per_player"] == 45.0


# ---------------------------------------------------------------------------
# Shared fixture helper
# ---------------------------------------------------------------------------


def _fake_db_conn(monkeypatch):
    """Context manager that stubs out get_conn so no real DB is hit."""
    import contextlib

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)

    @contextlib.contextmanager
    def _fake_get_conn():
        yield mock_conn

    monkeypatch.setattr(golfnow_adapter, "get_conn", _fake_get_conn)
    return contextlib.nullcontext()
