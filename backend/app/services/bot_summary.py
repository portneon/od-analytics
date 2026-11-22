"""Builds the compact summary posted back by bot/automation integrations
(e.g. the Zoho Cliq bot) after a CSV has finished processing. Reuses the
same analytics functions the dashboard uses -- never recomputed ad hoc --
and additionally renders a ready-to-post plain-text block, so the calling
integration (a Deluge script, in Cliq's case) doesn't need to do any
formatting of its own.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics import domains as domains_analytics
from app.core.config import settings
from app.analytics import overview as overview_analytics
from app.analytics import subjects as subjects_analytics
from app.intelligence.insights import generate_executive_insights
from app.models.dataset import Dataset


def build_bot_summary(db: Session, dataset: Dataset) -> dict:
    dataset_id = dataset.id
    channel = "whatsapp" if dataset.source == "whatsapp_gateway" else "email"
    unit_label = "messages" if channel == "whatsapp" else "emails"
    domain_label = "Institutes" if channel == "whatsapp" else "Domains"

    overview = overview_analytics.get_overview(db, dataset_id)
    top_domains = domains_analytics.list_domains(db, dataset_id, page=1, page_size=5, sort_by="total_emails")["items"]
    top_categories = subjects_analytics.list_subjects(db, dataset_id, page=1, page_size=5, sort_by="total_emails")["items"]
    insights = generate_executive_insights(db, dataset_id)

    quality = dataset.quality_report or {}

    lines: list[str] = []
    lines.append(f"*{dataset.name}* -- {channel.capitalize()} report")
    period = ""
    if dataset.date_start and dataset.date_end:
        period = f" ({dataset.date_start.date().isoformat()} to {dataset.date_end.date().isoformat()})"
    lines.append(f"{overview['total_emails']:,} {unit_label}{period}, {overview['unique_recipients']:,} unique recipients")
    lines.append(
        f"Delivery rate: {overview['delivery_rate']:.1f}%  |  Bounce rate: {overview['bounce_rate']:.1f}%  |  Failure rate: {overview['failure_rate']:.1f}%"
    )
    if quality.get("invalid_rows"):
        lines.append(f"Data quality: {quality['invalid_rows']:,} rows could not be parsed, {quality.get('duplicate_rows', 0):,} duplicates removed")

    if top_domains:
        lines.append("")
        lines.append(f"*Top {domain_label} by volume:*")
        for d in top_domains[:5]:
            lines.append(f"- {d['name']}: {d['total_emails']:,} ({d['failure_rate']:.1f}% failure)")

    if top_categories:
        lines.append("")
        lines.append("*Message categories:*")
        for c in top_categories[:5]:
            lines.append(f"- {c['name']}: {c['total_emails']:,}")

    if insights:
        lines.append("")
        lines.append("*Anomalies & recommendations:*")
        for insight in insights[:5]:
            change = f" ({insight['change_percent']:+.1f}%)" if insight.get("change_percent") is not None else ""
            lines.append(f"- [{insight['severity'].upper()}] {insight['title']}{change}")
    else:
        lines.append("")
        lines.append("No statistically significant anomalies detected.")

    if settings.FRONTEND_PUBLIC_URL:
        lines.append("")
        lines.append(f"Full dashboard: {settings.FRONTEND_PUBLIC_URL.rstrip('/')}/datasets/{dataset_id}")

    return {
        "dataset_id": str(dataset_id),
        "name": dataset.name,
        "status": dataset.status.value,
        "channel": channel,
        "row_count": dataset.row_count,
        "date_start": dataset.date_start.isoformat() if dataset.date_start else None,
        "date_end": dataset.date_end.isoformat() if dataset.date_end else None,
        "overview": overview,
        "domain_label": domain_label,
        "top_domains": top_domains,
        "top_categories": top_categories,
        "insights": insights,
        "summary_text": "\n".join(lines),
    }
