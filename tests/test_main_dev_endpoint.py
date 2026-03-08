from fastapi.testclient import TestClient

import main


def test_dev_simulate_sms_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(main, "_process_inbound_sms", lambda _: "test-reply")
    client = TestClient(main.app)

    resp = client.post(
        "/dev/simulate-sms",
        json={"from_number": "+19175550123", "body": "hello"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["reply_text"] == "test-reply"
    assert body["message_sid"].startswith("dev-")
