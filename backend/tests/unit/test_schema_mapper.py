from app.ingestion.schema_mapper import detect_schema


def test_detects_standard_zoho_columns():
    mapping = detect_schema(["FROM", "TO", "SUBJECT", "DATE", "STATUS", "REMOTE IP"])
    assert mapping.field_to_column["sender_email"] == "FROM"
    assert mapping.field_to_column["recipient_email"] == "TO"
    assert mapping.field_to_column["event_time"] == "DATE"
    assert mapping.missing_required_fields == []


def test_flags_missing_required_fields():
    mapping = detect_schema(["SUBJECT", "STATUS"])
    assert "sender_email" in mapping.missing_required_fields
    assert "recipient_email" in mapping.missing_required_fields
    assert "event_time" in mapping.missing_required_fields


def test_unmapped_columns_are_preserved_not_dropped():
    mapping = detect_schema(["FROM", "TO", "DATE", "SOME_CUSTOM_COLUMN"])
    assert "SOME_CUSTOM_COLUMN" in mapping.unmapped_columns


def test_case_and_whitespace_insensitive_matching():
    mapping = detect_schema(["  from  ", "To", "date"])
    assert mapping.has_field("sender_email")
    assert mapping.has_field("recipient_email")
    assert mapping.has_field("event_time")


def test_detects_real_zoho_export_headers():
    cols = ["PROCESSED TIME", "FROM", "SUBJECT", "TO", "DELIVERY INFO", "HARD BOUNCE", "SOFT BOUNCE", "MAIL FAILURE", "STATUS"]
    mapping = detect_schema(cols)
    assert mapping.field_to_column["event_time"] == "PROCESSED TIME"
    assert mapping.field_to_column["sender_email"] == "FROM"
    assert mapping.field_to_column["recipient_email"] == "TO"
    assert mapping.field_to_column["bounce_reason"] == "DELIVERY INFO"
    assert mapping.missing_required_fields == []
