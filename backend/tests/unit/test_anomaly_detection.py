from app.intelligence.anomaly_detection import _severity_for_abs_z, _z_score
from app.models.anomaly import AnomalySeverity


def test_z_score_basic():
    assert _z_score(10, 5, 5) == 1.0


def test_z_score_zero_std_returns_zero():
    assert _z_score(10, 5, 0) == 0.0


def test_severity_below_threshold_is_none():
    assert _severity_for_abs_z(1.0) is None


def test_severity_escalates_with_magnitude():
    low = _severity_for_abs_z(2.6)
    high = _severity_for_abs_z(4.5)
    assert low == AnomalySeverity.LOW
    assert high == AnomalySeverity.CRITICAL
