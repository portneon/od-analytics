"""Report generation (spec section 53): assembles an executive report from
the same analytics/intelligence functions the dashboard uses (never
recomputed ad hoc), then renders it as PDF or CSV.
"""
from __future__ import annotations

import csv
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.analytics import bounces as bounces_analytics
from app.analytics import domains as domains_analytics
from app.analytics import overview as overview_analytics
from app.analytics import recipients as recipients_analytics
from app.analytics import subjects as subjects_analytics
from app.intelligence.insights import generate_executive_insights
from app.models.dataset import Dataset


def build_report_data(db: Session, dataset: Dataset) -> dict:
    dataset_id = dataset.id
    channel = "whatsapp" if dataset.source == "whatsapp_gateway" else "email"
    overview = overview_analytics.get_overview(db, dataset_id)
    top_recipients = recipients_analytics.list_recipients(db, dataset_id, page=1, page_size=10, sort_by="failure_rate")["items"]
    # For WhatsApp the "domain" dimension actually holds the sending
    # institute (extracted from the message body by the WhatsApp adapter,
    # since the gateway's own Sender column is just the gateway's number)
    # -- still meaningful, just not a DNS domain, so it's included for both
    # channels. WhatsApp delivery outcomes are never classified as SMTP
    # bounces though, so bounce_reasons legitimately stays empty there.
    domain_label = "Institutes" if channel == "whatsapp" else "Domains"
    top_domains = domains_analytics.list_domains(db, dataset_id, page=1, page_size=10, sort_by="bounce_rate")["items"]
    top_subjects = subjects_analytics.list_subjects(db, dataset_id, page=1, page_size=10, sort_by="failure_rate")["items"]
    bounce_reasons = [] if channel == "whatsapp" else bounces_analytics.list_bounce_reasons(db, dataset_id)
    insights = generate_executive_insights(db, dataset_id)

    recommendations: list[str] = []
    for insight in insights:
        recommendations.extend(insight.get("recommendations", []))
    if not recommendations:
        recommendations.extend(_fallback_observations(top_recipients, top_domains, bounce_reasons, domain_label))
    if not recommendations:
        recommendations.append("No significant issues detected in this dataset.")

    return {
        "channel": channel,
        "domain_label": domain_label,
        "dataset": {
            "id": str(dataset.id),
            "name": dataset.name,
            "row_count": dataset.row_count,
            "date_start": dataset.date_start.isoformat() if dataset.date_start else None,
            "date_end": dataset.date_end.isoformat() if dataset.date_end else None,
        },
        "overview": overview,
        "top_problem_recipients": top_recipients,
        "top_problem_domains": top_domains,
        "top_problem_subjects": top_subjects,
        "bounce_reasons": bounce_reasons,
        "insights": insights,
        "recommendations": list(dict.fromkeys(recommendations)),  # de-dupe, preserve order
    }


def _fallback_observations(
    top_recipients: list[dict], top_domains: list[dict], bounce_reasons: list[dict], domain_label: str = "Domains"
) -> list[str]:
    """When no anomaly-based insight fired (e.g. too little history for
    statistical significance), still surface the plainest observations from
    data the report already has, so the export isn't just an empty note."""
    observations: list[str] = []

    if top_domains and top_domains[0].get("bounce_rate", 0) > 0:
        d = top_domains[0]
        observations.append(f"'{d.get('name')}' has the highest bounce rate among {domain_label.lower()} at {d.get('bounce_rate')}%.")

    if top_recipients and top_recipients[0].get("failure_rate", 0) > 0:
        r = top_recipients[0]
        observations.append(f"'{r.get('name')}' has the highest failure rate among recipients at {r.get('failure_rate')}%.")

    if bounce_reasons:
        top_reason = max(bounce_reasons, key=lambda b: b.get("count", 0))
        if top_reason.get("count", 0) > 0:
            observations.append(
                f"'{top_reason.get('business_label')}' is the most common bounce reason, accounting for {top_reason.get('percent_of_total')}% of bounces."
            )

    return observations


def render_pdf(report: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = []

    is_whatsapp = report.get("channel") == "whatsapp"
    unit_label = "Messages" if is_whatsapp else "Emails"
    channel_label = "WhatsApp" if is_whatsapp else "Email"
    domain_label = report.get("domain_label", "Domains")

    ds = report["dataset"]
    story.append(Paragraph(f"Executive {channel_label} Report — {ds['name']}", styles["Title"]))
    story.append(Paragraph(f"Period: {ds.get('date_start') or 'N/A'} to {ds.get('date_end') or 'N/A'} · {ds.get('row_count') or 0} events", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    ov = report["overview"]
    story.append(Paragraph("Overview", styles["Heading2"]))
    overview_table = [
        [f"Total {unit_label}", "Unique Recipients", "Delivery Rate", "Bounce Rate", "Failure Rate"],
        [str(ov["total_emails"]), str(ov["unique_recipients"]), f"{ov['delivery_rate']}%", f"{ov['bounce_rate']}%", f"{ov['failure_rate']}%"],
    ]
    story.append(_styled_table(overview_table))
    story.append(Spacer(1, 0.5 * cm))

    if report["top_problem_domains"]:
        story.append(Paragraph(f"Top Problem {domain_label}", styles["Heading2"]))
        story.append(_entity_table(report["top_problem_domains"], "name"))
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Top Problem Recipients", styles["Heading2"]))
    story.append(_entity_table(report["top_problem_recipients"], "name"))
    story.append(Spacer(1, 0.5 * cm))

    if is_whatsapp:
        story.append(Paragraph("Delivery Failures", styles["Heading2"]))
        story.append(Paragraph(
            "WhatsApp delivery failures aren't classified into SMTP-style bounce categories — "
            "see the Events tab filtered to the FAILED status for individual failure reasons.",
            styles["Normal"],
        ))
    elif report["bounce_reasons"]:
        story.append(Paragraph("Bounce Reasons", styles["Heading2"]))
        bounce_rows = [["Category", "Count", "% of bounces"]] + [
            [b["business_label"], str(b["count"]), f"{b['percent_of_total']}%"] for b in report["bounce_reasons"][:10]
        ]
        story.append(_styled_table(bounce_rows))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Key Insights", styles["Heading2"]))
    if report["insights"]:
        for insight in report["insights"]:
            change = f" ({insight['change_percent']:+.1f}%)" if insight["change_percent"] is not None else ""
            story.append(Paragraph(f"<b>[{insight['severity'].upper()}] {insight['title']}</b>{change}", styles["Normal"]))
            if insight.get("explanation"):
                story.append(Paragraph(insight["explanation"], styles["Normal"]))
            if insight.get("observed") is not None and insight.get("baseline") is not None:
                story.append(Paragraph(f"Observed {insight['observed']} vs. baseline {insight['baseline']}", styles["Normal"]))
            for c in insight.get("contributors", []):
                story.append(Paragraph(f"— {c['dimension']} '{c['value']}' contributed {c['contribution_percent']}%", styles["Normal"]))
            story.append(Spacer(1, 0.25 * cm))
    else:
        story.append(Paragraph("No statistically significant anomalies detected in this dataset.", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Recommendations", styles["Heading2"]))
    for rec in report["recommendations"]:
        story.append(Paragraph(f"• {rec}", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()


def _entity_table(items: list[dict], name_key: str):
    rows = [["Name", "Total", "Bounce Rate", "Failure Rate"]]
    for item in items[:10]:
        rows.append([str(item.get(name_key, "")), str(item.get("total_emails", 0)), f"{item.get('bounce_rate', 0)}%", f"{item.get('failure_rate', 0)}%"])
    return _styled_table(rows)


def _styled_table(rows: list[list[str]]) -> Table:
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ]))
    return table


def render_csv(report: dict) -> str:
    is_whatsapp = report.get("channel") == "whatsapp"
    domain_label = report.get("domain_label", "Domains")
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["Section", "Metric", "Value"])
    for key, value in report["overview"].items():
        writer.writerow(["Overview", key, value])
    writer.writerow([])

    # SMTP-style bounce classification doesn't exist for a phone-number-
    # addressed channel like WhatsApp -- that section is dropped below
    # rather than written out as a permanently-empty table. The domain/
    # institute section applies to both channels (see domain_label above).
    if report["top_problem_domains"]:
        writer.writerow([f"Top Problem {domain_label}"])
        writer.writerow([domain_label[:-1] if domain_label.endswith("s") else domain_label, "Total", "Delivery Rate", "Bounce Rate", "Failure Rate"])
        for d in report["top_problem_domains"]:
            writer.writerow([d["name"], d["total_emails"], d["delivery_rate"], d["bounce_rate"], d["failure_rate"]])
        writer.writerow([])

    writer.writerow(["Top Problem Recipients"])
    writer.writerow(["Recipient", "Total", "Delivery Rate", "Bounce Rate", "Failure Rate", "Risk Score"])
    for r in report["top_problem_recipients"]:
        writer.writerow([r["name"], r["total_emails"], r["delivery_rate"], r["bounce_rate"], r["failure_rate"], r.get("risk_score")])
    writer.writerow([])

    if is_whatsapp:
        writer.writerow(["Delivery Failures"])
        writer.writerow([
            "WhatsApp delivery failures aren't classified into SMTP-style bounce categories "
            "-- see the Events export filtered to the FAILED status for individual failure reasons."
        ])
        writer.writerow([])
    elif report["bounce_reasons"]:
        writer.writerow(["Bounce Reasons"])
        writer.writerow(["Category", "Business Label", "Count", "% of Bounces"])
        for b in report["bounce_reasons"]:
            writer.writerow([b["bounce_category"], b["business_label"], b["count"], b["percent_of_total"]])
        writer.writerow([])

    writer.writerow(["Key Insights"])
    writer.writerow(["Severity", "Title", "Metric", "Observed", "Baseline", "Change %", "Explanation", "Contributors"])
    for insight in report["insights"]:
        contributors = "; ".join(
            f"{c['dimension']}={c['value']} ({c['contribution_percent']}%)" for c in insight.get("contributors", [])
        )
        writer.writerow([
            insight["severity"],
            insight["title"],
            insight["metric"],
            insight["observed"],
            insight["baseline"],
            insight["change_percent"],
            insight.get("explanation") or "",
            contributors,
        ])
    if not report["insights"]:
        writer.writerow(["No statistically significant anomalies detected in this dataset."])
    writer.writerow([])

    writer.writerow(["Recommendations"])
    for rec in report["recommendations"]:
        writer.writerow([rec])

    return buffer.getvalue()
