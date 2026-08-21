from __future__ import annotations

from pydantic import BaseModel, Field


class IssueSample(BaseModel):
    row_index: int
    field: str
    issue: str
    raw_value: str | None = None


class DataQualityReport(BaseModel):
    rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    retry_rows: int = 0

    malformed_emails: int = 0
    missing_timestamps: int = 0
    missing_recipient: int = 0
    missing_bounce_information: int = 0

    # Engagement data (opens/clicks) is a source-schema question, not a
    # computed metric -- if the CSV never had the columns, we must say so
    # rather than report a fabricated 0.
    missing_open_data: bool = True
    missing_click_data: bool = True

    unmapped_source_columns: list[str] = Field(default_factory=list)
    missing_optional_fields: list[str] = Field(default_factory=list)

    issue_samples: list[IssueSample] = Field(default_factory=list, description="Up to 50 representative issues")
