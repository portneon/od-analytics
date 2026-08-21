"""Deterministic bounce classification.

Rule-based, in priority order:
  1. Enhanced SMTP status code (RFC 3463, e.g. "5.1.1") -> exact/prefix lookup.
  2. SMTP class digit (4xx = transient/soft, 5xx = permanent/hard) as a type hint.
  3. Keyword matching against the raw bounce reason text.
  4. Fall back to UNKNOWN. Only at that point is this a candidate for the
     optional AI fallback classifier (see app.ai.bounce_ai_fallback) -- the
     AI is never consulted for a case the rules already resolved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.email_event import BounceCategory, BounceSeverity, BounceType

# Enhanced status code (class.subject.detail) -> category. Keyed by the
# "subject.detail" portion (e.g. "1.1") since the class digit (4 vs 5) only
# ever changes hard/soft, never the underlying reason category.
_CODE_SUBJECT_DETAIL_CATEGORY: dict[str, BounceCategory] = {
    "1.1": BounceCategory.MAILBOX_NOT_FOUND,
    "1.2": BounceCategory.MAILBOX_NOT_FOUND,
    "1.6": BounceCategory.MAILBOX_NOT_FOUND,
    "1.0": BounceCategory.INVALID_DOMAIN,
    "1.3": BounceCategory.INVALID_DOMAIN,
    "1.7": BounceCategory.INVALID_DOMAIN,
    "1.8": BounceCategory.INVALID_DOMAIN,
    "1.10": BounceCategory.INVALID_DOMAIN,
    "2.1": BounceCategory.MAILBOX_FULL,
    "2.2": BounceCategory.MAILBOX_FULL,
    "2.3": BounceCategory.MAILBOX_FULL,
    "3.4": BounceCategory.MAILBOX_FULL,
    "4.4": BounceCategory.DNS_ERROR,
    "4.6": BounceCategory.DNS_ERROR,
    "4.7": BounceCategory.DNS_ERROR,
    "4.1": BounceCategory.TEMPORARY_FAILURE,
    "4.2": BounceCategory.TEMPORARY_FAILURE,
    "4.3": BounceCategory.TEMPORARY_FAILURE,
    "4.0": BounceCategory.TEMPORARY_FAILURE,
    "7.1": BounceCategory.POLICY_REJECTION,
    "7.7": BounceCategory.SPAM_REJECTION,
    "7.5": BounceCategory.AUTHENTICATION_FAILURE,
    "7.6": BounceCategory.AUTHENTICATION_FAILURE,
    "7.8": BounceCategory.AUTHENTICATION_FAILURE,
    "7.9": BounceCategory.AUTHENTICATION_FAILURE,
    "7.0": BounceCategory.BLOCKED,
}

_SEVERITY_BY_CATEGORY: dict[BounceCategory, BounceSeverity] = {
    BounceCategory.MAILBOX_NOT_FOUND: BounceSeverity.HIGH,
    BounceCategory.INVALID_DOMAIN: BounceSeverity.HIGH,
    BounceCategory.MAILBOX_FULL: BounceSeverity.MEDIUM,
    BounceCategory.RATE_LIMITED: BounceSeverity.LOW,
    BounceCategory.POLICY_REJECTION: BounceSeverity.MEDIUM,
    BounceCategory.SPAM_REJECTION: BounceSeverity.HIGH,
    BounceCategory.DNS_ERROR: BounceSeverity.MEDIUM,
    BounceCategory.TEMPORARY_FAILURE: BounceSeverity.LOW,
    BounceCategory.AUTHENTICATION_FAILURE: BounceSeverity.HIGH,
    BounceCategory.BLOCKED: BounceSeverity.HIGH,
    BounceCategory.NONE: BounceSeverity.NONE,
    BounceCategory.UNKNOWN: BounceSeverity.LOW,
}

# Applied, in order, to the lowercased bounce reason text when no usable SMTP
# code is present. First match wins.
_KEYWORD_RULES: list[tuple[re.Pattern, BounceCategory]] = [
    (re.compile(r"no such user|user unknown|does not exist|invalid recipient|unknown user|recipient rejected"),
     BounceCategory.MAILBOX_NOT_FOUND),
    (re.compile(r"no such domain|domain not found|host not found|invalid domain"), BounceCategory.INVALID_DOMAIN),
    (re.compile(r"mailbox full|over quota|quota exceeded|storage limit"), BounceCategory.MAILBOX_FULL),
    (re.compile(r"rate limit|too many (messages|connections)|throttl"), BounceCategory.RATE_LIMITED),
    (re.compile(r"spam|blacklist|reputation|content rejected"), BounceCategory.SPAM_REJECTION),
    (re.compile(r"blocked|access denied|banned|refused"), BounceCategory.BLOCKED),
    (re.compile(r"policy|not authorized|relay(ing)? denied"), BounceCategory.POLICY_REJECTION),
    (re.compile(r"authentication|spf|dkim|dmarc"), BounceCategory.AUTHENTICATION_FAILURE),
    (re.compile(r"dns|mx record|temporary dns"), BounceCategory.DNS_ERROR),
    (re.compile(r"try again|temporarily deferred|greylist|temporary failure"), BounceCategory.TEMPORARY_FAILURE),
]

_ENHANCED_CODE_RE = re.compile(r"^([245])\.(\d{1,3})\.(\d{1,3})$")


@dataclass
class BounceClassification:
    smtp_code: str | None
    bounce_type: BounceType
    category: BounceCategory
    severity: BounceSeverity


def _type_from_class_digit(class_digit: str) -> BounceType:
    if class_digit == "5":
        return BounceType.HARD
    if class_digit == "4":
        return BounceType.SOFT
    return BounceType.NONE


def _type_from_hint(status_hint: str | None) -> BounceType:
    if not status_hint:
        return BounceType.NONE
    hint = status_hint.lower()
    if "hard" in hint:
        return BounceType.HARD
    if "soft" in hint or "defer" in hint:
        return BounceType.SOFT
    return BounceType.NONE


def classify_bounce(
    *,
    smtp_code: str | None,
    reason_text: str | None,
    status_hint: str | None = None,
) -> BounceClassification:
    """Classify a bounce from whatever signals the source row provides.

    `smtp_code` should be the enhanced status code if the source has one
    (e.g. "5.1.1"); `status_hint` is any free-text status column value
    (e.g. "Hard Bounce", "Delivered"); `reason_text` is the raw diagnostic
    message.
    """
    smtp_code = (smtp_code or "").strip() or None
    reason_text = (reason_text or "").strip() or None

    if smtp_code:
        match = _ENHANCED_CODE_RE.match(smtp_code)
        if match:
            class_digit, subject, detail = match.groups()
            bounce_type = _type_from_class_digit(class_digit)
            category = _CODE_SUBJECT_DETAIL_CATEGORY.get(f"{subject}.{detail}")
            if category:
                return BounceClassification(smtp_code, bounce_type, category, _SEVERITY_BY_CATEGORY[category])

    bounce_type = _type_from_hint(status_hint) or _type_from_hint(smtp_code)

    if reason_text:
        lowered = reason_text.lower()
        for pattern, category in _KEYWORD_RULES:
            if pattern.search(lowered):
                if bounce_type == BounceType.NONE:
                    bounce_type = BounceType.HARD if category in (
                        BounceCategory.MAILBOX_NOT_FOUND, BounceCategory.INVALID_DOMAIN,
                        BounceCategory.SPAM_REJECTION, BounceCategory.BLOCKED,
                        BounceCategory.AUTHENTICATION_FAILURE,
                    ) else BounceType.SOFT
                return BounceClassification(smtp_code, bounce_type, category, _SEVERITY_BY_CATEGORY[category])

    if bounce_type == BounceType.NONE and not smtp_code and not reason_text:
        return BounceClassification(smtp_code, BounceType.NONE, BounceCategory.NONE, BounceSeverity.NONE)

    return BounceClassification(smtp_code, bounce_type, BounceCategory.UNKNOWN, _SEVERITY_BY_CATEGORY[BounceCategory.UNKNOWN])
