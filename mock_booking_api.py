from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


def _slot_to_hour(slot: str) -> int:
    mapping = {
        "early_morning": 8,
        "late_morning": 10,
        "early_afternoon": 12,
    }
    return mapping.get(slot, 10)


def search_tee_times(
    target_date: date,
    time_windows: list[str],
    courses: list[str],
    group_size: int,
    max_results: int = 3,
) -> list[dict[str, object]]:
    if not courses or not time_windows:
        return []

    base_date = datetime.combine(target_date, time(0, 0), tzinfo=timezone.utc)
    price_base = 38 + (group_size * 3)

    results: list[dict[str, object]] = []
    for course_idx, course in enumerate(courses):
        for slot_idx, slot in enumerate(time_windows):
            start_hour = _slot_to_hour(slot)
            tee_time = base_date + timedelta(hours=start_hour + (slot_idx * 0.5))
            price = price_base + (course_idx * 9)
            results.append(
                {
                    "course": course,
                    "tee_time": tee_time,
                    "price_per_player": float(price),
                    "booking_url": (
                        f"https://booking.mock.golf/checkout?course={course.replace(' ', '+')}"
                        f"&date={target_date.isoformat()}&slot={slot}&players={group_size}"
                    ),
                }
            )

    results.sort(key=lambda item: (item["tee_time"], item["price_per_player"]))
    return results[:max_results]
