"""JSON-schema tool definitions exposed to the LLM (spec section 49).

The LLM only ever sees these schemas -- it can request a tool call, but the
actual query is always executed by app.ai.tools.executor against the real
database, scoped to the dataset_id fixed by the API request (never supplied
by the LLM). This is what prevents the AI from fabricating numbers or
querying outside the current dataset.
"""
from __future__ import annotations

TOOLS: list[dict] = [
    {"name": "get_overview", "description": "Get overall volume and delivery/bounce/failure rate metrics for the dataset.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_daily_metrics", "description": "Get the day-by-day email volume and delivery/bounce/failure rate timeline.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_hourly_metrics", "description": "Get email volume and rates aggregated by hour of day (0-23).", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "get_recipient_metrics",
        "description": "List recipients with their volume, delivery/bounce/failure rates, and risk score, sorted by a metric.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["total_emails", "bounce_rate", "failure_rate", "delivery_rate"]},
                "limit": {"type": "integer", "description": "Max rows to return, default 20, max 100"},
            },
        },
    },
    {
        "name": "get_domain_metrics",
        "description": "List recipient domains with volume, delivery/bounce/failure rates.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["total_emails", "bounce_rate", "failure_rate", "delivery_rate"]},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_subject_metrics",
        "description": "List email subjects with volume, delivery/bounce/failure rates.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["total_emails", "bounce_rate", "failure_rate", "delivery_rate"]},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_sender_metrics",
        "description": "List senders with volume, delivery/bounce/failure rates.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["total_emails", "bounce_rate", "failure_rate", "delivery_rate"]},
                "limit": {"type": "integer"},
            },
        },
    },
    {"name": "get_bounce_reasons", "description": "Get bounce counts broken down by category/SMTP code with business-friendly labels.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_anomalies", "description": "Get statistically detected anomalies (volume/bounce-rate/failure-rate spikes) for the dataset.", "parameters": {"type": "object", "properties": {}}},
    {
        "name": "get_recipient_profile",
        "description": "Get the full profile (metrics, risk score, recent event timeline) for one recipient by email address.",
        "parameters": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
    },
    {
        "name": "get_domain_profile",
        "description": "Get the full profile (metrics) for one recipient domain, e.g. 'gmail.com'.",
        "parameters": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]},
    },
    {
        "name": "compare_periods",
        "description": "Compare volume and rate metrics between two date ranges within the dataset.",
        "parameters": {
            "type": "object",
            "properties": {
                "period_a_start": {"type": "string", "format": "date"},
                "period_a_end": {"type": "string", "format": "date"},
                "period_b_start": {"type": "string", "format": "date"},
                "period_b_end": {"type": "string", "format": "date"},
            },
            "required": ["period_a_start", "period_a_end", "period_b_start", "period_b_end"],
        },
    },
    {
        "name": "search_email_events",
        "description": "Search individual email events with filters (recipient, domain, subject text, status, bounce type, date range). Returns up to 50 matching events.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_email": {"type": "string"},
                "domain": {"type": "string"},
                "subject_contains": {"type": "string"},
                "status": {"type": "string", "enum": ["SUCCESS", "HARD_BOUNCE", "SOFT_BOUNCE", "FAILED", "DEFERRED", "UNKNOWN"]},
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"},
            },
        },
    },
    {"name": "get_application_metrics", "description": "Get volume and rates broken down by application/workflow category (e.g. Attendance, Payment, Admission).", "parameters": {"type": "object", "properties": {}}},
]
