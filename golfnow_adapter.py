from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger("golf-agent")


def search_tee_times(
    target_date: date,
    time_windows: list[str],
    courses: list[str],
    group_size: int,
    max_results: int = 3,
) -> list[dict[str, object]]:
    # Placeholder adapter until GolfNow credentials/API wiring is implemented.
    logger.info(
        "golfnow_adapter_not_configured target_date=%s courses=%s windows=%s group_size=%s max_results=%s",
        target_date,
        len(courses),
        len(time_windows),
        group_size,
        max_results,
    )
    return []
