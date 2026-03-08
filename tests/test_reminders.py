from datetime import datetime, timedelta, timezone

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
