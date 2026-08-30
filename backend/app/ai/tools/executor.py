"""Binds each AI tool name to a real analytics/database call, scoped to a
fixed dataset_id captured at executor-creation time. The LLM supplies only
the declared arguments (sort_by, limit, filters, dates) -- never dataset_id.
"""
from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import application as application_analytics
from app.analytics import bounces as bounces_analytics
from app.analytics import domains as domains_analytics
from app.analytics import overview as overview_analytics
from app.analytics import recipients as recipients_analytics
from app.analytics import senders as senders_analytics
from app.analytics import subjects as subjects_analytics
from app.analytics import timeline as timeline_analytics
from app.analytics.rates import compute_rates
from app.models.anomaly import Anomaly
from app.models.dimensions import Domain, Recipient, Subject
from app.models.email_event import EmailEvent
from app.models.metrics import DailyEmailMetrics

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
MAX_SEARCH_RESULTS = 50


def _clamp_limit(limit) -> int:
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIST_LIMIT
    return max(1, min(limit, MAX_LIST_LIMIT))


def build_executor(db: Session, dataset_id: uuid.UUID):
    def _get_overview(_args: dict) -> dict:
        return overview_analytics.get_overview(db, dataset_id)

    def _get_daily_metrics(_args: dict) -> dict:
        return {"days": timeline_analytics.get_daily_timeline(db, dataset_id)}

    def _get_hourly_metrics(_args: dict) -> dict:
        return {"hours": timeline_analytics.get_hourly_timeline(db, dataset_id)}

    def _get_recipient_metrics(args: dict) -> dict:
        result = recipients_analytics.list_recipients(
            db, dataset_id, page=1, page_size=_clamp_limit(args.get("limit", DEFAULT_LIST_LIMIT)),
            sort_by=args.get("sort_by", "total_emails"),
        )
        return {"recipients": result["items"], "total": result["total"]}

    def _get_domain_metrics(args: dict) -> dict:
        result = domains_analytics.list_domains(
            db, dataset_id, page=1, page_size=_clamp_limit(args.get("limit", DEFAULT_LIST_LIMIT)),
            sort_by=args.get("sort_by", "total_emails"),
        )
        return {"domains": result["items"], "total": result["total"]}

    def _get_subject_metrics(args: dict) -> dict:
        result = subjects_analytics.list_subjects(
            db, dataset_id, page=1, page_size=_clamp_limit(args.get("limit", DEFAULT_LIST_LIMIT)),
            sort_by=args.get("sort_by", "total_emails"),
        )
        return {"subjects": result["items"], "total": result["total"]}

    def _get_sender_metrics(args: dict) -> dict:
        result = senders_analytics.list_senders(
            db, dataset_id, page=1, page_size=_clamp_limit(args.get("limit", DEFAULT_LIST_LIMIT)),
            sort_by=args.get("sort_by", "total_emails"),
        )
        return {"senders": result["items"], "total": result["total"]}

    def _get_bounce_reasons(_args: dict) -> dict:
        return {"bounce_reasons": bounces_analytics.list_bounce_reasons(db, dataset_id)}

    def _get_anomalies(_args: dict) -> dict:
        rows = db.execute(
            select(Anomaly).where(Anomaly.dataset_id == dataset_id).order_by(Anomaly.detected_at.desc())
        ).scalars().all()
        return {"anomalies": [
            {
                "metric": a.metric, "entity_type": a.entity_type, "entity_id": a.entity_id,
                "observed_value": a.observed_value, "expected_value": a.expected_value,
                "severity": a.severity.value, "explanation": a.explanation,
            }
            for a in rows
        ]}

    def _get_recipient_profile(args: dict) -> dict:
        email = (args.get("email") or "").strip().lower()
        recipient = db.execute(select(Recipient).where(Recipient.email == email)).scalar_one_or_none()
        if recipient is None:
            return {"error": f"No recipient found with email '{email}' in this dataset"}
        profile = recipients_analytics.get_recipient_profile(db, dataset_id, recipient.id)
        return profile or {"error": "Recipient has no activity in this dataset"}

    def _get_domain_profile(args: dict) -> dict:
        domain_value = (args.get("domain") or "").strip().lower()
        domain = db.execute(select(Domain).where(Domain.domain == domain_value)).scalar_one_or_none()
        if domain is None:
            return {"error": f"No domain found matching '{domain_value}' in this dataset"}
        profile = domains_analytics.get_domain_profile(db, dataset_id, domain.id)
        return profile or {"error": "Domain has no activity in this dataset"}

    def _compare_periods(args: dict) -> dict:
        def _sum_period(start: date_type, end: date_type) -> dict:
            stmt = select(
                func.coalesce(func.sum(DailyEmailMetrics.total_emails), 0),
                func.coalesce(func.sum(DailyEmailMetrics.successful), 0),
                func.coalesce(func.sum(DailyEmailMetrics.hard_bounces), 0),
                func.coalesce(func.sum(DailyEmailMetrics.soft_bounces), 0),
                func.coalesce(func.sum(DailyEmailMetrics.failures), 0),
            ).where(
                DailyEmailMetrics.dataset_id == dataset_id,
                DailyEmailMetrics.date >= start, DailyEmailMetrics.date <= end,
            )
            total, succ, hard, soft, fail = (int(v) for v in db.execute(stmt).one())
            return {"total_emails": total, "successful": succ, "hard_bounces": hard, "soft_bounces": soft, "failures": fail,
                    **compute_rates(total=total, successful=succ, hard_bounces=hard, soft_bounces=soft, failures=fail)}

        try:
            period_a = _sum_period(date_type.fromisoformat(args["period_a_start"]), date_type.fromisoformat(args["period_a_end"]))
            period_b = _sum_period(date_type.fromisoformat(args["period_b_start"]), date_type.fromisoformat(args["period_b_end"]))
        except (KeyError, ValueError) as exc:
            return {"error": f"Invalid or missing date arguments: {exc}"}
        return {"period_a": period_a, "period_b": period_b}

    def _search_email_events(args: dict) -> dict:
        filters = [EmailEvent.dataset_id == dataset_id]
        if args.get("recipient_email"):
            filters.append(EmailEvent.recipient_email == args["recipient_email"].strip().lower())
        if args.get("domain"):
            filters.append(EmailEvent.recipient_email.ilike(f"%@{args['domain'].strip().lower()}"))
        if args.get("status"):
            filters.append(EmailEvent.status == args["status"])
        if args.get("date_from"):
            filters.append(EmailEvent.event_time >= date_type.fromisoformat(args["date_from"]))
        if args.get("date_to"):
            filters.append(EmailEvent.event_time <= date_type.fromisoformat(args["date_to"]))

        stmt = select(EmailEvent).where(*filters)
        if args.get("subject_contains"):
            stmt = stmt.join(Subject, Subject.id == EmailEvent.subject_id).where(Subject.subject.ilike(f"%{args['subject_contains']}%"))

        rows = db.execute(stmt.order_by(EmailEvent.event_time.desc()).limit(MAX_SEARCH_RESULTS)).scalars().all()
        return {"events": [
            {
                "id": str(e.id), "event_time": e.event_time.isoformat(), "sender_email": e.sender_email,
                "recipient_email": e.recipient_email, "status": e.status.value,
                "bounce_category": e.bounce_category.value if hasattr(e.bounce_category, "value") else e.bounce_category,
            }
            for e in rows
        ], "result_count": len(rows), "truncated": len(rows) == MAX_SEARCH_RESULTS}

    def _get_application_metrics(_args: dict) -> dict:
        return {"applications": application_analytics.list_application_metrics(db, dataset_id)}

    registry = {
        "get_overview": _get_overview,
        "get_daily_metrics": _get_daily_metrics,
        "get_hourly_metrics": _get_hourly_metrics,
        "get_recipient_metrics": _get_recipient_metrics,
        "get_domain_metrics": _get_domain_metrics,
        "get_subject_metrics": _get_subject_metrics,
        "get_sender_metrics": _get_sender_metrics,
        "get_bounce_reasons": _get_bounce_reasons,
        "get_anomalies": _get_anomalies,
        "get_recipient_profile": _get_recipient_profile,
        "get_domain_profile": _get_domain_profile,
        "compare_periods": _compare_periods,
        "search_email_events": _search_email_events,
        "get_application_metrics": _get_application_metrics,
    }

    def executor(tool_name: str, arguments: dict):
        handler = registry.get(tool_name)
        if handler is None:
            return {"error": f"Unknown tool '{tool_name}'"}
        try:
            return handler(arguments or {})
        except Exception as exc:  # noqa: BLE001 - tool errors are returned to the LLM, not raised
            return {"error": f"Tool execution failed: {exc}"}

    return executor
