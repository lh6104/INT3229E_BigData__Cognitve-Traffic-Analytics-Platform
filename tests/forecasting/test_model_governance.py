import pytest

from cognitive_traffic.forecasting.inference import congestion_probability
from cognitive_traffic.forecasting.training import PromotionGate


def test_promotion_requires_quality_and_baseline_improvement() -> None:
    gate = PromotionGate(maximum_peak_mae=10)
    approved = gate.evaluate(
        candidate_mae=5,
        baseline_mae=7,
        champion_mae=5.1,
        peak_mae=8,
        leakage_passed=True,
        data_quality_passed=True,
        schema_compatible=True,
    )
    assert approved.approved is True

    rejected = gate.evaluate(
        candidate_mae=8,
        baseline_mae=7,
        champion_mae=5,
        peak_mae=12,
        leakage_passed=False,
        data_quality_passed=True,
        schema_compatible=True,
    )
    assert rejected.approved is False
    assert len(rejected.reasons) >= 3


def test_risk_is_explicit_probability_from_quantiles() -> None:
    assert congestion_probability(threshold_kmh=10, p10=10, p50=20, p90=30) == pytest.approx(0.1)
    assert congestion_probability(threshold_kmh=20, p10=10, p50=20, p90=30) == pytest.approx(0.5)
    assert congestion_probability(threshold_kmh=30, p10=10, p50=20, p90=30) == pytest.approx(0.9)
