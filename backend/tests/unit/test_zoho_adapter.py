import polars as pl

from app.ingestion.adapters.zoho import ZohoAdapter
from app.ingestion.schema_mapper import detect_schema

COLUMNS = ["FROM", "TO", "SUBJECT", "DATE", "STATUS"]


def _parse(rows: list[list[str]]):
    df = pl.DataFrame(rows, schema=COLUMNS, orient="row")
    adapter = ZohoAdapter()
    mapping = detect_schema(COLUMNS)
    return list(adapter.parse(df, mapping, dataset_id="d1"))


def test_comma_separated_recipients_fan_out_into_multiple_valid_events():
    parsed = _parse([[
        "alerts@acme.com",
        "a@gmail.com, b@gmail.com,c@gmail.com",
        "Attendance Alert",
        "2026-07-01 09:00:00",
        "Delivered",
    ]])

    assert len(parsed) == 3
    recipients = {p.event.recipient for p in parsed}
    assert recipients == {"a@gmail.com", "b@gmail.com", "c@gmail.com"}
    assert all(p.is_valid for p in parsed)
    assert all(p.row_index == 0 for p in parsed)


def test_semicolon_separated_recipients_also_split():
    parsed = _parse([[
        "alerts@acme.com",
        "a@gmail.com;b@gmail.com",
        "Attendance Alert",
        "2026-07-01 09:00:00",
        "Delivered",
    ]])

    assert {p.event.recipient for p in parsed} == {"a@gmail.com", "b@gmail.com"}


def test_one_malformed_recipient_in_the_list_does_not_drop_the_valid_ones():
    parsed = _parse([[
        "alerts@acme.com",
        "a@gmail.com, not-an-email",
        "Attendance Alert",
        "2026-07-01 09:00:00",
        "Delivered",
    ]])

    assert len(parsed) == 2
    valid = [p for p in parsed if p.is_valid]
    invalid = [p for p in parsed if not p.is_valid]
    assert len(valid) == 1
    assert valid[0].event.recipient == "a@gmail.com"
    assert len(invalid) == 1
    assert any(i.issue == "malformed_email" for i in invalid[0].issues)


def test_single_recipient_unaffected():
    parsed = _parse([[
        "alerts@acme.com",
        "a@gmail.com",
        "Attendance Alert",
        "2026-07-01 09:00:00",
        "Delivered",
    ]])

    assert len(parsed) == 1
    assert parsed[0].event.recipient == "a@gmail.com"
    assert parsed[0].is_valid
