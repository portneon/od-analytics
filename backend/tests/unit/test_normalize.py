from app.ingestion.normalize import extract_domain, is_valid_email, normalize_email, normalize_empty, parse_timestamp


def test_normalize_empty_blanks_to_none():
    assert normalize_empty("") is None
    assert normalize_empty("   ") is None
    assert normalize_empty(None) is None
    assert normalize_empty(" x ") == "x"


def test_normalize_email_lowercases_and_trims():
    assert normalize_email("  Foo@Example.COM ") == "foo@example.com"
    assert normalize_email("") is None


def test_is_valid_email():
    assert is_valid_email("foo@example.com") is True
    assert is_valid_email("not-an-email") is False
    assert is_valid_email("") is False
    assert is_valid_email(None) is False


def test_extract_domain():
    assert extract_domain("foo@example.com") == "example.com"
    assert extract_domain("foo@Example.COM") == "example.com"
    assert extract_domain(None) is None
    assert extract_domain("not-an-email") is None


def test_parse_timestamp_known_formats():
    assert parse_timestamp("2026-07-01 10:00:00").year == 2026
    assert parse_timestamp("01/07/2026 10:00:00 AM") is not None
    assert parse_timestamp("") is None
    assert parse_timestamp(None) is None


def test_parse_timestamp_unparseable_returns_none():
    assert parse_timestamp("not a date at all !!") is None
