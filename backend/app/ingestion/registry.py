from __future__ import annotations

from app.ingestion.adapters.base import SourceAdapter
from app.ingestion.adapters.whatsapp import WhatsAppGatewayAdapter
from app.ingestion.adapters.zoho import ZohoAdapter
from app.ingestion.schema_mapper import normalize_header

_ADAPTERS: dict[str, SourceAdapter] = {
    "zoho_mail": ZohoAdapter(),
    "whatsapp_gateway": WhatsAppGatewayAdapter(),
}

# Minimum number of an adapter's signature_columns that must appear in an
# uploaded file's header before auto-detection will route to it instead of
# the caller-given default.
_SIGNATURE_MATCH_THRESHOLD = 4


def get_adapter(source: str) -> SourceAdapter:
    adapter = _ADAPTERS.get(source)
    if adapter is None:
        raise ValueError(f"No ingestion adapter registered for source '{source}'")
    return adapter


def available_sources() -> list[str]:
    return list(_ADAPTERS.keys())


def detect_source(columns: list[str], *, default: str) -> str:
    """Best-effort auto-detection of which registered adapter a CSV belongs
    to, based on its header row -- used because uploads don't carry an
    explicit source choice today. Only ever routes *to* an adapter whose
    signature clearly matches; never routes away from the caller's default,
    so an explicit choice is never second-guessed."""
    normalized = {normalize_header(c) for c in columns}
    best_source = default
    best_score = _SIGNATURE_MATCH_THRESHOLD - 1
    for name, adapter in _ADAPTERS.items():
        if name == default or not adapter.signature_columns:
            continue
        score = len(adapter.signature_columns & normalized)
        if score > best_score:
            best_score = score
            best_source = name
    return best_source
