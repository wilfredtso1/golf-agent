from __future__ import annotations

SEED_GOLF_COURSE_PROFILES: list[dict[str, object]] = [
    {
        "name": "Maple Moor",
        "metadata": {"region": "Westchester", "provider": "golfnow", "tags": ["public", "18-hole"]},
    },
    {
        "name": "Silver Lake",
        "metadata": {"region": "Staten Island", "provider": "golfnow", "tags": ["public", "18-hole"]},
    },
    {
        "name": "La Tourette",
        "metadata": {"region": "Staten Island", "provider": "golfnow", "tags": ["public", "18-hole"]},
    },
    {
        "name": "Dyker",
        "metadata": {"region": "Brooklyn", "provider": "golfnow", "tags": ["public", "18-hole"]},
    },
    {
        "name": "Pelham",
        "metadata": {"region": "Bronx", "provider": "golfnow", "tags": ["public", "18-hole"]},
    },
    {
        "name": "Saxon Woods",
        "metadata": {"region": "Westchester", "provider": "golfnow", "tags": ["public", "18-hole"]},
    },
    {
        "name": "Forest Hills",
        "metadata": {"region": "Queens", "provider": "golfnow", "tags": ["public", "9-hole"]},
    },
]

SEED_GOLF_COURSES: list[str] = [str(item["name"]) for item in SEED_GOLF_COURSE_PROFILES]
