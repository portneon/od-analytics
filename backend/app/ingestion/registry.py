from __future__ import annotations

from app.ingestion.adapters.base import SourceAdapter
from app.ingestion.adapters.zoho import ZohoAdapter

_ADAPTERS: dict[str, SourceAdapter] = {
    "zoho_mail": ZohoAdapter(),
}


def get_adapter(source: str) -> SourceAdapter:
    adapter = _ADAPTERS.get(source)
    if adapter is None:
        raise ValueError(f"No ingestion adapter registered for source '{source}'")
    return adapter


def available_sources() -> list[str]:
    return list(_ADAPTERS.keys())
