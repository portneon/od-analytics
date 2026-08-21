"""Field-level normalization helpers shared by every source adapter."""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

from app.core.config import settings

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DEFAULT_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)

# Timestamp formats tried in order before falling back to dateutil's fuzzy parser.
_KNOWN_TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%d/%m/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M:%S %p",
    "%d-%m-%Y %I:%M:%S %p",
    "%d %b %Y %H:%M:%S",
    "%Y-%m-%d",
]


def normalize_empty(value: str | None) -> str | None:
    """Blank / whitespace-only strings become None so downstream code has a
    single consistent representation of "missing" instead of "" vs None.
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def normalize_email(value: str | None) -> str | None:
    value = normalize_empty(value)
    if value is None:
        return None
    return value.strip().lower()


def is_valid_email(value: str | None) -> bool:
    if not value:
        return False
    return bool(_EMAIL_RE.match(value))


def extract_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[-1].strip().lower() or None


def parse_timestamp(value: str | None) -> datetime | None:
    """Source exports (Zoho et al.) almost never include a UTC offset --
    timestamps are plain local wall-clock time. A naive result here would
    later be handed to Postgres, whose interpretation of "naive" depends on
    the server's own session TimeZone GUC, which has no guaranteed relation
    to the tenant's actual timezone (settings.DEFAULT_TIMEZONE) -- in most
    real deployments (cloud Postgres defaults to UTC) that mismatch would
    silently shift every daily/hourly/day-of-week bucket. So: localize here,
    in Python, once, and only trust an offset already present in the source
    value itself.
    """
    value = normalize_empty(value)
    if value is None:
        return None
    parsed: datetime | None = None
    for fmt in _KNOWN_TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = date_parser.parse(value)
        except (ValueError, OverflowError, date_parser.ParserError):
            return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=_DEFAULT_TZ)
