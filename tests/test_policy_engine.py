from policy_engine import evaluate_session, intersect_courses, intersect_time_blocks, minimum_group_size_met


def _session() -> dict[str, object]:
    return {
        "candidate_courses": ["Bethpage", "Marine Park", "Dyker Beach"],
        "players": [
            {
                "status": "confirmed",
                "approved_courses": ["Bethpage", "Marine Park"],
                "available_time_blocks": ["early_morning", "late_morning"],
            },
            {
                "status": "confirmed",
                "approved_courses": ["Marine Park", "Bethpage"],
                "available_time_blocks": ["late_morning", "early_afternoon"],
            },
            {
                "status": "invited",
                "approved_courses": ["Dyker Beach"],
                "available_time_blocks": ["early_afternoon"],
            },
        ],
    }


def test_minimum_group_size_met() -> None:
    assert minimum_group_size_met(_session()) is True


def test_intersections() -> None:
    session = _session()
    assert intersect_courses(session) == ["Bethpage", "Marine Park"]
    assert intersect_time_blocks(session) == ["late_morning"]


def test_evaluate_session() -> None:
    policy = evaluate_session(_session())
    assert policy["minimum_group_size_met"] is True
    assert policy["has_overlap"] is True
    assert policy["confirmed_count"] == 2
