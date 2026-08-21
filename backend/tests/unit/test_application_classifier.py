from app.ingestion.application_classifier import CategoryRule, classify_subject


def test_default_rules_classify_known_subjects():
    assert classify_subject("Attendance Alert - absent today") == "Attendance"
    assert classify_subject("Payment Reminder - fee due") == "Payment"
    assert classify_subject("Admission Confirmation") == "Admission"


def test_unmatched_subject_falls_back_to_other():
    assert classify_subject("Random subject with no keywords") == "Other"


def test_none_subject_returns_other():
    assert classify_subject(None) == "Other"


def test_custom_rules_override_defaults():
    rules = [CategoryRule(category="Custom", match_type="contains", pattern="widget", priority=1)]
    assert classify_subject("New Widget Available", rules) == "Custom"
    assert classify_subject("Unrelated subject", rules) == "Other"
