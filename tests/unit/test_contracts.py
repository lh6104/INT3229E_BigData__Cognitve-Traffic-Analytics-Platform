from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from cognitive_traffic.contracts.events import deterministic_event_id
from cognitive_traffic.contracts.forecasts import Forecast
from cognitive_traffic.contracts.traffic import TrafficObservation

NOW = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)


def observation(source_record_id: str = "provider-1") -> TrafficObservation:
    return TrafficObservation.create(
        road_id="HN-001",
        city="hanoi",
        event_time=NOW,
        ingested_at=NOW + timedelta(seconds=4),
        speed_kmh=24,
        free_flow_speed_kmh=45,
        source="tomtom",
        source_record_id=source_record_id,
    )


def test_event_id_is_stable_across_replay() -> None:
    assert observation().event_id == observation().event_id
    assert observation("provider-2").event_id != observation().event_id


def test_deterministic_id_normalizes_timezone() -> None:
    vietnam_time = NOW.astimezone(timezone(timedelta(hours=7)))
    assert deterministic_event_id(source="x", entity_id="r", event_time=NOW) == deterministic_event_id(
        source="x", entity_id="r", event_time=vietnam_time
    )


def test_naive_event_time_is_rejected() -> None:
    with pytest.raises((ValueError, ValidationError), match="timezone"):
        TrafficObservation.create(
            road_id="HN-001",
            city="hanoi",
            event_time=datetime(2026, 8, 12, 8),
            ingested_at=NOW,
            speed_kmh=24,
            free_flow_speed_kmh=45,
            source="tomtom",
        )


def test_forecast_quantiles_and_target_order_are_enforced() -> None:
    base = dict(
        event_id="forecast-1",
        road_id="HN-001",
        city="hanoi",
        event_time=NOW,
        ingested_at=NOW,
        prediction_time=NOW,
        target_time=NOW + timedelta(minutes=15),
        horizon_minutes=15,
        model_version="7",
        feature_version="1",
        source="forecast-service",
        p10_speed_kmh=15,
        p50_speed_kmh=20,
        p90_speed_kmh=28,
    )
    assert Forecast(**base).p50_speed_kmh == 20
    with pytest.raises(ValidationError, match="p10 <= p50 <= p90"):
        Forecast(**{**base, "p10_speed_kmh": 25})
