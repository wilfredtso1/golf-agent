from __future__ import annotations

import logging
from datetime import date

from config import SETTINGS
from golfnow_adapter import search_tee_times as search_golfnow_tee_times
from mock_booking_api import search_tee_times as search_mock_tee_times

logger = logging.getLogger("golf-agent")


def search_tee_times(
    target_date: date,
    time_windows: list[str],
    courses: list[str],
    group_size: int,
    max_results: int = 3,
) -> list[dict[str, object]]:
    provider = SETTINGS.tee_time_provider
    if provider == "golfnow":
        try:
            rows = search_golfnow_tee_times(
                target_date=target_date,
                time_windows=time_windows,
                courses=courses,
                group_size=group_size,
                max_results=max_results,
            )
            if rows:
                return rows
            logger.warning("golfnow_provider_empty_result_fallback provider=golfnow")
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("golfnow_provider_error_fallback provider=golfnow error=%s", exc)
    return search_mock_tee_times(
        target_date=target_date,
        time_windows=time_windows,
        courses=courses,
        group_size=group_size,
        max_results=max_results,
    )
