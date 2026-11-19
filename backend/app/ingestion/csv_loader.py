"""CSV file loading & structural validation, before any semantic parsing.

Everything is read as strings deliberately -- type coercion (int/float/date)
happens later, per-field, in the adapter, where we can record a data-quality
issue instead of having polars silently produce a null on a type mismatch.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from app.core.config import settings


class CsvValidationError(Exception):
    pass


@dataclass
class LoadedCsv:
    df: pl.DataFrame
    columns: list[str]
    row_count: int


def validate_upload(file_name: str, file_size_bytes: int) -> None:
    suffix = Path(file_name).suffix.lower()
    if suffix not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise CsvValidationError(f"Unsupported file extension '{suffix}'. Allowed: {settings.ALLOWED_UPLOAD_EXTENSIONS}")
    if file_size_bytes <= 0:
        raise CsvValidationError("Uploaded file is empty")
    if file_size_bytes > settings.MAX_UPLOAD_FILE_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_FILE_SIZE_BYTES / (1024 * 1024)
        raise CsvValidationError(f"File exceeds maximum allowed size of {max_mb:.0f}MB")


def sniff_header(content: bytes) -> list[str]:
    """Peek at just the header row of an uploaded file, before the full
    polars parse -- used to auto-detect which source adapter a CSV belongs
    to. Never raises: an unreadable/empty header just yields no columns,
    which detect_source treats as "no match"."""
    try:
        text = content.decode("utf-8-sig", errors="ignore")
    except Exception:  # noqa: BLE001 - best-effort sniffing only
        return []
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if not first_line:
        return []
    try:
        return next(csv.reader(io.StringIO(first_line)))
    except (csv.Error, StopIteration):
        return []


def load_csv(file_path: str) -> LoadedCsv:
    try:
        df = pl.read_csv(
            file_path,
            infer_schema=False,
            ignore_errors=False,
            truncate_ragged_lines=True,
            encoding="utf8-lossy",
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to caller as a validation error
        raise CsvValidationError(f"Failed to parse CSV: {exc}") from exc

    if df.width == 0:
        raise CsvValidationError("CSV file has no columns")
    if df.height == 0:
        raise CsvValidationError("CSV file has no data rows")

    return LoadedCsv(df=df, columns=df.columns, row_count=df.height)
