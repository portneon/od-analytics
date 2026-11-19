from app.ingestion.registry import detect_source

ZOHO_COLUMNS = ["FROM", "TO", "SUBJECT", "DATE", "STATUS", "REMOTE IP"]

WABA_COLUMNS = [
    "Sender",
    "Recipient",
    "Accept Date & Time",
    "Sent Date & Time",
    "Delivered Date & Time",
    "Read Date & Time",
    "Status",
    "Error description",
    "Template ID",
    "ACK ID",
    "MID",
    "Waba Pricing Category",
]


def test_zoho_shaped_header_stays_on_default():
    assert detect_source(ZOHO_COLUMNS, default="zoho_mail") == "zoho_mail"


def test_waba_shaped_header_is_routed_to_whatsapp_gateway():
    assert detect_source(WABA_COLUMNS, default="zoho_mail") == "whatsapp_gateway"


def test_a_couple_of_incidental_overlaps_do_not_trigger_a_false_match():
    # Only "Template ID" and "ACK ID" happen to overlap -- nowhere near
    # enough signal to leave the caller's chosen default.
    assert detect_source(["FROM", "TO", "DATE", "Template ID", "ACK ID"], default="zoho_mail") == "zoho_mail"


def test_never_overrides_an_explicit_non_default_choice():
    assert detect_source(ZOHO_COLUMNS, default="whatsapp_gateway") == "whatsapp_gateway"
