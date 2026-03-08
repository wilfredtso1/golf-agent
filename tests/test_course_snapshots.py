from unittest.mock import MagicMock

from tools import upsert_course_snapshot


def test_upsert_course_snapshot_executes_insert_with_conflict() -> None:
    cur = MagicMock()
    upsert_course_snapshot(
        cur,
        name="Maple Moor",
        booking_url="https://booking.example/maple",
        price_per_player=72.0,
    )

    # table ensure + insert
    assert cur.execute.call_count >= 2
    final_sql = cur.execute.call_args_list[-1].args[0]
    assert "INSERT INTO courses" in final_sql
    assert "ON CONFLICT (name) DO UPDATE" in final_sql
