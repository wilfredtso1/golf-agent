from uuid import uuid4
from unittest.mock import MagicMock

from tools import get_recent_messages


def test_get_recent_messages_uses_player_only_query_when_session_missing() -> None:
    cur = MagicMock()
    cur.fetchall.return_value = []

    get_recent_messages(cur, session_id=None, player_id=uuid4(), limit=10)

    sql = cur.execute.call_args.args[0]
    assert "AND session_id = %s" not in sql
    assert "WHERE player_id = %s" in sql


def test_get_recent_messages_limits_upper_bound() -> None:
    cur = MagicMock()
    cur.fetchall.return_value = []

    get_recent_messages(cur, session_id=uuid4(), player_id=uuid4(), limit=9999)

    params = cur.execute.call_args.args[1]
    assert params[-1] == 200
