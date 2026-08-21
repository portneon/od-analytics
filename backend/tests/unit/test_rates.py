from app.analytics.rates import compute_rates, safe_rate


def test_safe_rate_zero_denominator():
    assert safe_rate(5, 0) == 0.0


def test_safe_rate_normal():
    assert safe_rate(1, 4) == 25.0


def test_compute_rates_shape():
    rates = compute_rates(total=100, successful=80, hard_bounces=10, soft_bounces=5, failures=5)
    assert rates["delivery_rate"] == 80.0
    assert rates["bounce_rate"] == 15.0
    assert rates["failure_rate"] == 5.0


def test_compute_rates_zero_total():
    rates = compute_rates(total=0, successful=0, hard_bounces=0, soft_bounces=0, failures=0)
    assert rates == {"delivery_rate": 0.0, "bounce_rate": 0.0, "failure_rate": 0.0}
