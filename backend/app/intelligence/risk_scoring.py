"""Recipient risk engine (spec section 40).

Produces an explainable 0-100 risk_score per recipient plus a risk_level and
a human-readable list of contributing reasons -- never just a bare number.
Weights and saturation points are configuration (app.core.config), not
magic numbers buried in the formula.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import bindparam, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.email_event import EmailEvent, EmailStatus
from app.models.metrics import RecipientMetrics, RiskLevel

logger = get_logger(__name__)

_FAILURE_STATUSES = {EmailStatus.HARD_BOUNCE, EmailStatus.SOFT_BOUNCE, EmailStatus.FAILED}

# Saturation points: the count/streak at which that component of the score
# hits its full weight. Chosen conservatively (a handful of hard bounces is
# already a strong signal); tune further later if needed.
HARD_BOUNCE_SATURATION = 5
SOFT_BOUNCE_SATURATION = 10
FAILURE_STREAK_SATURATION = 5
RECENCY_HALF_LIFE_DAYS = 7  # recency component halves every this many days since last failure


@dataclass
class RecipientRiskResult:
    recipient_id: uuid.UUID
    score: float
    level: RiskLevel
    reasons: list[str] = field(default_factory=list)


def _level_for_score(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 35:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _failure_streak(statuses_desc: list[EmailStatus]) -> int:
    """Count consecutive failures starting from the most recent event."""
    streak = 0
    for status in statuses_desc:
        if status in _FAILURE_STATUSES:
            streak += 1
        else:
            break
    return streak


def _score_recipient(
    *, total: int, hard: int, soft: int, failures: int, streak: int, last_failure_at: datetime | None, as_of: datetime
) -> tuple[float, list[str]]:
    reasons: list[str] = []

    hard_component = min(hard / HARD_BOUNCE_SATURATION, 1.0) * 100
    if hard:
        reasons.append(f"{hard} hard bounce{'s' if hard != 1 else ''}")

    soft_component = min(soft / SOFT_BOUNCE_SATURATION, 1.0) * 100
    if soft:
        reasons.append(f"{soft} soft bounce{'s' if soft != 1 else ''}")

    failure_rate_pct = (failures / total * 100) if total else 0.0
    failure_rate_component = failure_rate_pct
    if failures:
        reasons.append(f"{failure_rate_pct:.0f}% failure rate ({failures} of {total} attempts)")

    streak_component = min(streak / FAILURE_STREAK_SATURATION, 1.0) * 100
    if streak >= 2:
        reasons.append(f"{streak} consecutive recent failures")

    recency_component = 0.0
    if last_failure_at is not None:
        days_since = max((as_of - last_failure_at).total_seconds() / 86400, 0)
        recency_component = 100 * (0.5 ** (days_since / RECENCY_HALF_LIFE_DAYS))
        if days_since < 1:
            reasons.append("Last failure occurred today")
        elif days_since < 3:
            reasons.append(f"Last failure occurred {days_since:.0f} days ago")

    score = (
        hard_component * settings.RISK_WEIGHT_HARD_BOUNCE
        + soft_component * settings.RISK_WEIGHT_SOFT_BOUNCE
        + failure_rate_component * settings.RISK_WEIGHT_FAILURE_RATE
        + streak_component * settings.RISK_WEIGHT_FAILURE_STREAK
        + recency_component * settings.RISK_WEIGHT_RECENCY
    )
    return round(min(score, 100.0), 1), reasons


def calculate_recipient_risk(db: Session, dataset_id: uuid.UUID) -> int:
    stmt = (
        select(EmailEvent.recipient_id, EmailEvent.event_time, EmailEvent.status)
        .where(
            EmailEvent.dataset_id == dataset_id,
            EmailEvent.recipient_id.is_not(None),
        )
        .order_by(EmailEvent.recipient_id, EmailEvent.event_time.desc())
    )
    rows = db.execute(stmt).all()
    if not rows:
        return 0

    as_of = max(r[1] for r in rows)

    grouped: dict[uuid.UUID, list[tuple[datetime, EmailStatus]]] = {}
    for recipient_id, event_time, status in rows:
        grouped.setdefault(recipient_id, []).append((event_time, status))

    results: list[dict] = []
    for recipient_id, events in grouped.items():
        # events already sorted desc by event_time (query ordering preserved per group)
        statuses_desc = [s for _, s in events]
        total = len(events)
        hard = sum(1 for _, s in events if s == EmailStatus.HARD_BOUNCE)
        soft = sum(1 for _, s in events if s == EmailStatus.SOFT_BOUNCE)
        failures = sum(1 for _, s in events if s in _FAILURE_STATUSES)
        streak = _failure_streak(statuses_desc)
        last_failure_at = next((t for t, s in events if s in _FAILURE_STATUSES), None)

        score, reasons = _score_recipient(
            total=total, hard=hard, soft=soft, failures=failures, streak=streak,
            last_failure_at=last_failure_at, as_of=as_of,
        )
        results.append({
            "b_dataset_id": dataset_id,
            "b_recipient_id": recipient_id,
            "b_risk_score": score,
            "b_risk_level": _level_for_score(score),
            "b_risk_reasons": reasons,
        })

    # Built against RecipientMetrics.__table__ (Core), not the mapped class, so this is a
    # plain executemany-style bulk UPDATE rather than SQLAlchemy 2.0's ORM-enabled bulk
    # UPDATE-by-primary-key, which requires every param row to carry the row's own `id`.
    table = RecipientMetrics.__table__
    stmt = (
        update(table)
        .where(
            table.c.dataset_id == bindparam("b_dataset_id"),
            table.c.recipient_id == bindparam("b_recipient_id"),
        )
        .values(risk_score=bindparam("b_risk_score"), risk_level=bindparam("b_risk_level"), risk_reasons=bindparam("b_risk_reasons"))
    )
    db.execute(stmt, results)
    db.flush()
    logger.info("risk.calculated", dataset_id=str(dataset_id), recipients=len(results))
    return len(results)
