from datetime import datetime, timedelta, timezone

import reminders
from reminders import classify_reminder_action


def test_classify_reminder_none_before_4h() -> None:
    now = datetime.now(timezone.utc)
    invited_at = now - timedelta(hours=3, minutes=59)
    assert classify_reminder_action(invited_at, None, now) == "none"


def test_classify_reminder_at_4h_without_prior_reminder() -> None:
    now = datetime.now(timezone.utc)
    invited_at = now - timedelta(hours=4)
    assert classify_reminder_action(invited_at, None, now) == "remind"


def test_classify_reminder_none_if_already_reminded_before_8h() -> None:
    now = datetime.now(timezone.utc)
    invited_at = now - timedelta(hours=6)
    reminder_sent_at = now - timedelta(hours=2)
    assert classify_reminder_action(invited_at, reminder_sent_at, now) == "none"


def test_classify_escalate_at_8h() -> None:
    now = datetime.now(timezone.utc)
    invited_at = now - timedelta(hours=8, minutes=1)
    assert classify_reminder_action(invited_at, None, now) == "escalate"


def test_safe_send_sms_logs_on_failure(monkeypatch, caplog) -> None:
    def _raise(*_args, **_kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(reminders, "send_sms", _raise)

    with caplog.at_level("ERROR", logger="golf-agent"):
        sid = reminders._safe_send_sms("+19175550123", "hello")

    assert sid is None
    assert "Reminder SMS send failed" in caplog.text
    assert "***0123" in caplog.text
