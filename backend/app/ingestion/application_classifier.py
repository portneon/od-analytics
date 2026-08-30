"""Subject -> application/workflow category classification.

Ships with sensible default keyword rules (evaluated in order, first match
wins) but they can be overridden/extended via `ApplicationCategoryRule`
rows -- this module never hardcodes the category list as the only
possibility, it's just the out-of-the-box default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_CATEGORY = "Other"

# (category, match_type, pattern) -- mirrors ApplicationCategoryRule shape so
# DB-configured rules and these defaults can share evaluation logic.
DEFAULT_RULES: list[tuple[str, str, str]] = [
    ("Attendance", "contains", "attendance"),
    ("Payment", "contains", "payment"),
    ("Payment", "contains", "invoice"),
    ("Payment", "contains", "fee due"),
    ("Payment", "contains", "receipt"),
    ("Admission", "contains", "admission"),
    ("Admission", "contains", "enrollment"),
    ("Employee", "contains", "employee"),
    ("Employee", "contains", "payroll"),
    ("Employee", "contains", "onboarding"),
    ("ERP", "contains", "erp"),
    ("Notification", "contains", "notification"),
    ("Notification", "contains", "alert"),
    ("Notification", "contains", "reminder"),
    ("Cron", "contains", "cron"),
    ("Cron", "contains", "scheduled report"),
    ("Cron", "contains", "daily report"),
]


@dataclass
class CategoryRule:
    category: str
    match_type: str  # contains | starts_with | regex
    pattern: str
    priority: int = 100


def _matches(rule_pattern: str, match_type: str, subject_lower: str) -> bool:
    if match_type == "contains":
        return rule_pattern.lower() in subject_lower
    if match_type == "starts_with":
        return subject_lower.startswith(rule_pattern.lower())
    if match_type == "regex":
        return re.search(rule_pattern, subject_lower, re.IGNORECASE) is not None
    return False


def classify_subject(subject: str | None, rules: list[CategoryRule] | None = None) -> str:
    if not subject:
        return DEFAULT_CATEGORY

    subject_lower = subject.lower()
    ordered_rules = sorted(rules, key=lambda r: r.priority) if rules else [
        CategoryRule(category=cat, match_type=mt, pattern=pat) for cat, mt, pat in DEFAULT_RULES
    ]
    for rule in ordered_rules:
        if _matches(rule.pattern, rule.match_type, subject_lower):
            return rule.category
    return DEFAULT_CATEGORY
