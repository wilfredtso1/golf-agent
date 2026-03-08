from __future__ import annotations

import logging
from datetime import date

from course_semantic import resolve_course_candidates
from db import get_conn
from tools import list_courses

logger = logging.getLogger("golf-agent")


def search_tee_times(
    target_date: date,
    time_windows: list[str],
    courses: list[str],
    group_size: int,
    max_results: int = 3,
) -> list[dict[str, object]]:
    catalog_names: list[str] = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            catalog_names = [row["name"] for row in list_courses(cur, limit=500)]
    mapped_courses = resolve_course_candidates(courses, catalog_names)

    # Placeholder adapter until GolfNow credentials/API wiring is implemented.
    logger.info(
        "golfnow_adapter_not_configured target_date=%s requested_courses=%s mapped_courses=%s windows=%s group_size=%s max_results=%s",
        target_date,
        len(courses),
        len(mapped_courses),
        len(time_windows),
        group_size,
        max_results,
    )
    return []
