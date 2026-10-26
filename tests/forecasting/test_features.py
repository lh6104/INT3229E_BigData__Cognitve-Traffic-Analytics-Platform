from datetime import UTC, datetime, timedelta

import pytest

from cognitive_traffic.contracts.traffic import TrafficObservation
from cognitive_traffic.forecasting.features import (
    FEATURE_REGISTRY,
    PointInTimeFeatureBuilder,
    assert_point_in_time_correct,
)

NOW = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)


def item(minutes: int, speed: float, *, available_delay: int = 0) -> TrafficObservation:
    event_time = NOW + timedelta(minutes=minutes)
    return TrafficObservation.create(
        road_id="HN-001",
        city="hanoi",
        event_time=event_time,
        ingested_at=event_time + timedelta(minutes=available_delay),
        available_at=event_time + timedelta(minutes=available_delay),
        speed_kmh=speed,
        free_flow_speed_kmh=45,
        source="fixture",
        source_record_id=str(minutes),
    )


def test_rolling_features_exclude_future_and_unavailable_values() -> None:
    features = PointInTimeFeatureBuilder().build(
        road_id="HN-001",
        city="hanoi",
        prediction_time=NOW,
        traffic=[item(-30, 30), item(-10, 20), item(0, 10), item(1, 100), item(-1, 1, available_delay=5)],
    )
    assert features.speed_kmh == 10
    assert features.speed_mean_15m == 15
    assert features.speed_mean_30m == 20
    assert features.speed_change_kmh == -20


def test_feature_registry_declares_availability_rule() -> None:
    assert FEATURE_REGISTRY
    assert all(item.version and item.source for item in FEATURE_REGISTRY.values())
    assert all(item.availability_rule == "available_at <= prediction_time" for item in FEATURE_REGISTRY.values())


def test_point_in_time_guard_rejects_leakage() -> None:
    with pytest.raises(ValueError, match="unavailable"):
        assert_point_in_time_correct(
            prediction_time=NOW,
            feature_available_at=[NOW - timedelta(minutes=1), NOW + timedelta(seconds=1)],
            target_at=NOW + timedelta(minutes=15),
        )
