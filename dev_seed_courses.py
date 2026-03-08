from __future__ import annotations

from courses import SEED_GOLF_COURSE_PROFILES
from db import get_conn
from tools import upsert_course_snapshot


def main() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            for course in SEED_GOLF_COURSE_PROFILES:
                upsert_course_snapshot(
                    cur,
                    name=str(course["name"]),
                    booking_url=None,
                    price_per_player=None,
                    metadata=course.get("metadata") if isinstance(course, dict) else None,
                )
    print(f"SEEDED_COURSES={len(SEED_GOLF_COURSE_PROFILES)}")


if __name__ == "__main__":
    main()
