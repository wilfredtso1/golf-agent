from fastapi.testclient import TestClient

import main


def test_courses_endpoint_includes_count_and_payload(monkeypatch) -> None:
    fake_rows = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "Maple Moor",
            "default_booking_url": "https://booking.example/maple",
            "latest_price_per_player": 72,
            "latest_currency": "USD",
            "latest_seen_at": None,
            "metadata": {"source": "test"},
        }
    ]

    monkeypatch.setattr(main, "list_courses", lambda *args, **kwargs: fake_rows)

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return _Cur()

    monkeypatch.setattr(main, "get_conn", lambda: _Conn())

    client = TestClient(main.app)
    resp = client.get("/api/courses?q=maple&limit=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert body["courses"][0]["name"] == "Maple Moor"
