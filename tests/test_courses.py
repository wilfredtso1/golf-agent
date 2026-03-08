from courses import SEED_GOLF_COURSE_PROFILES, SEED_GOLF_COURSES


def test_seed_course_list() -> None:
    assert SEED_GOLF_COURSES == [
        "Maple Moor",
        "Silver Lake",
        "La Tourette",
        "Dyker",
        "Pelham",
        "Saxon Woods",
        "Forest Hills",
    ]


def test_seed_course_profiles_include_metadata() -> None:
    assert len(SEED_GOLF_COURSE_PROFILES) == len(SEED_GOLF_COURSES)
    for item in SEED_GOLF_COURSE_PROFILES:
        assert isinstance(item["name"], str)
        assert isinstance(item.get("metadata"), dict)
