from datetime import datetime, timedelta, timezone

from app.ingestion.retry_detection import detect_retries
from app.schemas.canonical import CanonicalEmailEvent, CanonicalStatus


def _event(minutes_offset: int, recipient="to@example.com", subject="Hello") -> CanonicalEmailEvent:
    base = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
    return CanonicalEmailEvent(
        tenant_id="t1",
        dataset_id="d1",
        timestamp=base + timedelta(minutes=minutes_offset),
        sender="from@example.com",
        recipient=recipient,
        subject=subject,
        status=CanonicalStatus.SUCCESS,
    )


def test_single_send_is_not_a_retry():
    events = [_event(0)]
    result = detect_retries(events)
    assert result[0][2] is False  # is_retry


def test_repeated_send_within_window_is_marked_retry():
    events = [_event(0), _event(5)]
    result = detect_retries(events)
    assert result[0][2] is False
    assert result[1][2] is True
    assert result[0][0] == result[1][0]  # same retry_group_id


def test_repeated_send_outside_window_is_not_a_retry():
    events = [_event(0), _event(120)]  # 2 hours apart, window is 60 min
    result = detect_retries(events)
    assert result[0][2] is False
    assert result[1][2] is False


def test_different_recipients_are_independent_groups():
    events = [_event(0, recipient="a@example.com"), _event(5, recipient="b@example.com")]
    result = detect_retries(events)
    assert result[0][0] != result[1][0]
