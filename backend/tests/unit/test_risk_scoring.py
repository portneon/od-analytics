from datetime import datetime, timezone

from app.intelligence.risk_scoring import _level_for_score, _score_recipient
from app.models.metrics import RiskLevel


def test_clean_recipient_scores_low():
    score, reasons = _score_recipient(total=20, hard=0, soft=0, failures=0, streak=0, last_failure_at=None, as_of=datetime.now(timezone.utc))
    assert score < 10
    assert reasons == []


def test_recent_hard_bounces_score_high():
    now = datetime.now(timezone.utc)
    score, reasons = _score_recipient(total=10, hard=6, soft=0, failures=6, streak=5, last_failure_at=now, as_of=now)
    assert score >= 60
    assert any("hard bounce" in r for r in reasons)
    assert any("consecutive" in r for r in reasons)


def test_level_thresholds():
    assert _level_for_score(90) == RiskLevel.CRITICAL
    assert _level_for_score(65) == RiskLevel.HIGH
    assert _level_for_score(40) == RiskLevel.MEDIUM
    assert _level_for_score(10) == RiskLevel.LOW
