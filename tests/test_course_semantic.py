from course_semantic import resolve_course_candidates, score_course_match


def test_score_course_match_exact_name_is_highest() -> None:
    assert score_course_match("Maple Moor", "Maple Moor") == 1.0


def test_resolve_course_candidates_handles_partial_names() -> None:
    catalog = ["Maple Moor", "Silver Lake", "Saxon Woods"]
    resolved = resolve_course_candidates(["maple", "saxon"], catalog)
    assert resolved == ["Maple Moor", "Saxon Woods"]


def test_resolve_course_candidates_filters_low_score_matches() -> None:
    catalog = ["Maple Moor", "Silver Lake"]
    resolved = resolve_course_candidates(["totally unrelated course"], catalog, min_score=0.8)
    assert resolved == []
