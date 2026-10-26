from datetime import UTC, datetime, timedelta

from cognitive_traffic.contracts.traffic import TrafficObservation
from cognitive_traffic.streaming.processors import EventTimeFeatureProcessor

BASE = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)


def event(minute: int, speed: float, record_id: str | None = None) -> TrafficObservation:
    event_time = BASE + timedelta(minutes=minute)
    return TrafficObservation.create(
        road_id="HN-001",
        city="hanoi",
        event_time=event_time,
        ingested_at=event_time + timedelta(seconds=2),
        speed_kmh=speed,
        free_flow_speed_kmh=45,
        source="fixture",
        source_record_id=record_id or str(minute),
    )


def test_duplicate_and_late_events_have_explicit_outcomes() -> None:
    processor = EventTimeFeatureProcessor(watermark_delay=timedelta(minutes=2))
    first = event(10, 30)
    assert processor.process(first).status == "accepted"
    assert processor.process(first).status == "duplicate"
    assert processor.process(event(7, 20)).status == "late"


def test_out_of_order_event_inside_watermark_is_accepted() -> None:
    processor = EventTimeFeatureProcessor(watermark_delay=timedelta(minutes=5))
    processor.process(event(10, 30))
    result = processor.process(event(8, 20))
    assert result.status == "accepted"
    assert result.feature is not None


def test_out_of_order_sequence_has_event_time_rolling_values() -> None:
    processor = EventTimeFeatureProcessor(watermark_delay=timedelta(minutes=6))
    for item in [event(0, 40), event(10, 20), event(5, 30)]:
        assert processor.process(item).status == "accepted"

    result = processor.process(event(15, 10))

    assert result.status == "accepted"
    assert result.feature is not None
    assert result.feature.speed_mean_15m == 20
    assert result.feature.speed_mean_30m == 25
    assert result.feature.speed_mean_60m == 25


def test_replay_produces_deterministic_feature_values() -> None:
    sequence = [event(0, 40), event(5, 30), event(10, 20)]
    first = EventTimeFeatureProcessor()
    second = EventTimeFeatureProcessor()
    left = [first.process(item).feature.model_dump() for item in sequence]
    right = [second.process(item).feature.model_dump() for item in sequence]
    assert left == right
