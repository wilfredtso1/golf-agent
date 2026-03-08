from __future__ import annotations

from collections.abc import Iterable


def _normalize_values(values: Iterable[str]) -> set[str]:
    return {value.strip() for value in values if isinstance(value, str) and value.strip()}


def confirmed_players(session_state: dict[str, object]) -> list[dict[str, object]]:
    players = session_state.get("players") or []
    return [p for p in players if p.get("status") == "confirmed"]


def minimum_group_size_met(session_state: dict[str, object], min_size: int = 2) -> bool:
    return len(confirmed_players(session_state)) >= min_size


def intersect_courses(session_state: dict[str, object]) -> list[str]:
    confirmed = confirmed_players(session_state)
    if not confirmed:
        return []

    intersection: set[str] | None = None
    for player in confirmed:
        approved = _normalize_values(player.get("approved_courses") or [])
        if intersection is None:
            intersection = approved
        else:
            intersection &= approved

    if intersection is None:
        return []

    # Preserve candidate course ordering for deterministic user-facing output.
    candidate_courses = [c for c in session_state.get("candidate_courses") or [] if isinstance(c, str)]
    candidate_lower = {c.lower(): c for c in candidate_courses}
    normalized_intersection = {c.lower() for c in intersection}

    ordered = [candidate for candidate in candidate_courses if candidate.lower() in normalized_intersection]
    extras = sorted(intersection - set(ordered))
    return ordered + extras


def intersect_time_blocks(session_state: dict[str, object]) -> list[str]:
    confirmed = confirmed_players(session_state)
    if not confirmed:
        return []

    intersection: set[str] | None = None
    for player in confirmed:
        available = _normalize_values(player.get("available_time_blocks") or [])
        if intersection is None:
            intersection = available
        else:
            intersection &= available

    if not intersection:
        return []

    preferred_order = ["early_morning", "late_morning", "early_afternoon"]
    ordered = [slot for slot in preferred_order if slot in intersection]
    extras = sorted(intersection - set(ordered))
    return ordered + extras


def evaluate_session(session_state: dict[str, object]) -> dict[str, object]:
    confirmed = confirmed_players(session_state)
    course_overlap = intersect_courses(session_state)
    time_overlap = intersect_time_blocks(session_state)

    return {
        "confirmed_count": len(confirmed),
        "minimum_group_size_met": len(confirmed) >= 2,
        "course_overlap": course_overlap,
        "time_overlap": time_overlap,
        "has_overlap": bool(course_overlap and time_overlap),
    }
