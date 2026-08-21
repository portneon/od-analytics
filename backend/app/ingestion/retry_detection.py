"""Heuristic retry detection.

This is explicitly probabilistic: two sends with the same sender/recipient/
subject inside the retry window are *marked as a likely retry group*, not
asserted to be a confirmed retry. A legitimate distinct email that happens
to share a subject line within the window will be swept in too -- callers
(UI, AI) should present this as "probable retry", not fact.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import timedelta

from app.core.config import settings
from app.schemas.canonical import CanonicalEmailEvent


def _group_key(event: CanonicalEmailEvent) -> str:
    raw = f"{(event.sender or '').lower()}|{(event.recipient or '').lower()}|{(event.subject or '').strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def detect_retries(events: list[CanonicalEmailEvent]) -> dict[int, tuple[str, int, bool]]:
    """Returns {event_list_index: (retry_group_id, retry_count, is_retry)}.

    `events` should be pre-sorted or will be sorted internally by timestamp.
    retry_count is the 1-based position of that send within its group;
    is_retry is True for every occurrence after the first.
    """
    window = timedelta(minutes=settings.RETRY_WINDOW_MINUTES)
    buckets: dict[str, list[int]] = defaultdict(list)
    for idx, event in enumerate(events):
        if not event.recipient:
            continue
        buckets[_group_key(event)].append(idx)

    result: dict[int, tuple[str, int, bool]] = {}
    for group_key, indices in buckets.items():
        ordered = sorted(indices, key=lambda i: events[i].timestamp)
        window_start_idx = 0
        occurrence = 0
        anchor_time = None
        for pos, idx in enumerate(ordered):
            ts = events[idx].timestamp
            if anchor_time is None or ts - anchor_time > window:
                anchor_time = ts
                occurrence = 1
            else:
                occurrence += 1
            result[idx] = (group_key, occurrence, occurrence > 1)
    return result
