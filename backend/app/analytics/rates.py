"""Shared rate-calculation helpers so delivery/bounce/failure rate math is
defined exactly once."""
from __future__ import annotations


def safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 4)


def compute_rates(*, total: int, successful: int, hard_bounces: int, soft_bounces: int, failures: int) -> dict:
    return {
        "delivery_rate": safe_rate(successful, total),
        "bounce_rate": safe_rate(hard_bounces + soft_bounces, total),
        "failure_rate": safe_rate(failures, total),
    }
