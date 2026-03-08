from __future__ import annotations

from difflib import SequenceMatcher


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def _token_jaccard(a: str, b: str) -> float:
    a_set = set(_normalize(a).split())
    b_set = set(_normalize(b).split())
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def score_course_match(requested: str, candidate: str) -> float:
    req = _normalize(requested)
    cand = _normalize(candidate)
    if not req or not cand:
        return 0.0
    if req == cand:
        return 1.0
    return (0.65 * SequenceMatcher(None, req, cand).ratio()) + (0.35 * _token_jaccard(req, cand))


def resolve_course_candidates(
    requested_courses: list[str],
    catalog_courses: list[str],
    *,
    min_score: float = 0.55,
) -> list[str]:
    if not requested_courses or not catalog_courses:
        return []

    resolved: list[str] = []
    for requested in requested_courses:
        scored = sorted(
            ((name, score_course_match(requested, name)) for name in catalog_courses),
            key=lambda row: row[1],
            reverse=True,
        )
        if not scored:
            continue
        best_name, best_score = scored[0]
        if best_score >= min_score and best_name not in resolved:
            resolved.append(best_name)
    return resolved
