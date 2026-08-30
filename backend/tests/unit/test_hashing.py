from datetime import datetime, timezone

from app.ingestion.hashing import compute_raw_record_hash


def _hash(**overrides):
    base = dict(
        sender="from@example.com",
        recipient="to@example.com",
        subject="Hello",
        timestamp=datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc),
        mail_reference="ref-1",
    )
    base.update(overrides)
    return compute_raw_record_hash(**base)


def test_identical_inputs_produce_identical_hash():
    assert _hash() == _hash()


def test_different_recipient_changes_hash():
    assert _hash() != _hash(recipient="other@example.com")


def test_timestamp_bucketing_absorbs_small_jitter():
    h1 = _hash(timestamp=datetime(2026, 7, 1, 10, 0, 5, tzinfo=timezone.utc))
    h2 = _hash(timestamp=datetime(2026, 7, 1, 10, 0, 45, tzinfo=timezone.utc))
    assert h1 == h2  # same 60s bucket
