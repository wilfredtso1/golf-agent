from __future__ import annotations

from datetime import date

from config import SETTINGS
from golfnow_adapter import search_tee_times as search_golfnow_tee_times
from mock_booking_api import search_tee_times as search_mock_tee_times


def search_tee_times(
    target_date: date,
    time_windows: list[str],
    courses: list[str],
    group_size: int,
    max_results: int = 3,
) -> list[dict[str, object]]:
    provider = SETTINGS.tee_time_provider
    if provider == "golfnow":
        return search_golfnow_tee_times(
            target_date=target_date,
            time_windows=time_windows,
            courses=courses,
            group_size=group_size,
            max_results=max_results,
        )
    return search_mock_tee_times(
        target_date=target_date,
        time_windows=time_windows,
        courses=courses,
        group_size=group_size,
        max_results=max_results,
    )
