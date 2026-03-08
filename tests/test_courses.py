from courses import SEED_GOLF_COURSES


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
