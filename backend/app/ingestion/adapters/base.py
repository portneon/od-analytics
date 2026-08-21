"""Adapter interface every email-provider source must implement.

`Zoho CSV -> Zoho Adapter -> CanonicalEmailEvent` today; a Gmail, SES, or
SendGrid adapter tomorrow implements the same interface and the rest of the
platform (ETL, analytics, intelligence, AI) does not change at all.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

import polars as pl

from app.ingestion.schema_mapper import SchemaMapping
from app.schemas.canonical import ParsedRow


class SourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def detect(self, columns: list[str]) -> SchemaMapping:
        """Map source columns to canonical fields."""

    @abstractmethod
    def parse(
        self, df: pl.DataFrame, mapping: SchemaMapping, *, tenant_id: str, dataset_id: str
    ) -> Iterator[ParsedRow]:
        """Yield one ParsedRow per source row, in order. Never raises on a
        single bad row -- bad rows come back as ParsedRow(is_valid=False)."""
