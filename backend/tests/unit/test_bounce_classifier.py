from app.ingestion.bounce_classifier import classify_bounce
from app.models.email_event import BounceCategory, BounceType


def test_classifies_hard_bounce_from_smtp_code():
    result = classify_bounce(smtp_code="5.1.1", reason_text="550 5.1.1 no such user", status_hint=None)
    assert result.bounce_type == BounceType.HARD
    assert result.category == BounceCategory.MAILBOX_NOT_FOUND


def test_classifies_soft_bounce_mailbox_full():
    result = classify_bounce(smtp_code="4.2.2", reason_text="mailbox full", status_hint=None)
    assert result.bounce_type == BounceType.SOFT
    assert result.category == BounceCategory.MAILBOX_FULL


def test_classifies_from_keyword_when_no_smtp_code():
    result = classify_bounce(smtp_code=None, reason_text="550 no such user here", status_hint=None)
    assert result.category == BounceCategory.MAILBOX_NOT_FOUND
    assert result.bounce_type == BounceType.HARD


def test_no_reason_returns_none_category():
    result = classify_bounce(smtp_code=None, reason_text=None, status_hint=None)
    assert result.category == BounceCategory.NONE
    assert result.bounce_type == BounceType.NONE


def test_unrecognized_reason_returns_unknown():
    result = classify_bounce(smtp_code=None, reason_text="some totally novel failure mode", status_hint="hard bounce")
    assert result.category == BounceCategory.UNKNOWN
    assert result.bounce_type == BounceType.HARD


def test_spam_rejection_classified_high_severity():
    result = classify_bounce(smtp_code=None, reason_text="rejected due to spam content policy", status_hint=None)
    assert result.category == BounceCategory.SPAM_REJECTION
