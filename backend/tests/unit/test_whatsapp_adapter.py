import polars as pl

from app.ingestion.adapters.whatsapp import WhatsAppGatewayAdapter
from app.schemas.canonical import CanonicalStatus

COLUMNS = [
    "Sender",
    "Recipient",
    "Accept Date & Time",
    "Sent Date & Time",
    "Delivered Date & Time",
    "Read Date & Time",
    "Status",
    "Error description",
    "Template ID",
    "MID",
    "Waba Pricing Category",
]


def _parse(rows: list[list[str]]):
    df = pl.DataFrame(rows, schema=COLUMNS, orient="row")
    adapter = WhatsAppGatewayAdapter()
    mapping = adapter.detect(COLUMNS)
    return list(adapter.parse(df, mapping, dataset_id="d1"))


def _row(recipient="919999999999", status="Read", error="Read by the user", sent="2026-09-30 10:00:00"):
    return [
        "917015613714",
        recipient,
        "2026-09-30 09:59:00",
        sent,
        "2026-09-30 10:00:05",
        "2026-09-30 10:05:00",
        status,
        error,
        "fee_receipt2a",
        "mid-123",
        "utility",
    ]


def test_detect_maps_waba_columns_as_required_fields():
    adapter = WhatsAppGatewayAdapter()
    mapping = adapter.detect(COLUMNS)
    assert mapping.field_to_column["sender_email"] == "Sender"
    assert mapping.field_to_column["recipient_email"] == "Recipient"
    assert mapping.field_to_column["event_time"] == "Sent Date & Time"
    assert mapping.missing_required_fields == []


def test_read_and_delivered_and_sent_map_to_success():
    for status in ("Read", "Delivered", "Sent"):
        parsed = _parse([_row(status=status)])
        assert parsed[0].event.status == CanonicalStatus.SUCCESS
        assert parsed[0].is_valid


def test_not_sent_maps_to_failed_with_bounce_reason():
    parsed = _parse([_row(status="Not Sent", error="Invalid Recipient")])
    event = parsed[0].event
    assert event.status == CanonicalStatus.FAILED
    assert event.bounce_reason == "Invalid Recipient"


def test_error_description_not_carried_as_bounce_reason_on_success():
    parsed = _parse([_row(status="Read", error="Read by the user")])
    assert parsed[0].event.bounce_reason is None


def test_phone_numbers_used_as_sender_and_recipient_not_emails():
    parsed = _parse([_row(recipient="919050201095")])
    event = parsed[0].event
    assert event.sender == "917015613714"
    assert event.recipient == "919050201095"
    assert event.sender_domain is None
    assert event.recipient_domain is None


def test_malformed_recipient_phone_is_flagged_invalid():
    parsed = _parse([_row(recipient="not-a-phone-number")])
    assert not parsed[0].is_valid
    assert any(i.issue == "malformed_email" and i.field == "recipient_email" for i in parsed[0].issues)


def test_blank_sent_time_is_flagged_and_invalid():
    parsed = _parse([_row(sent=" ")])
    assert not parsed[0].is_valid
    assert any(i.field == "event_time" for i in parsed[0].issues)
