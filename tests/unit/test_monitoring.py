from datetime import UTC, datetime, timedelta

from cognitive_traffic.monitoring import StreamQualityWindow


def test_quality_snapshot_measures_failures_freshness_and_coverage() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    quality = StreamQualityWindow("traffic.observation.v1", expected_roads=147)
    quality.observe(status="accepted", event_time=now - timedelta(seconds=20), observed_at=now, road_id="HN-1")
    quality.observe(status="duplicate", event_time=now - timedelta(seconds=10), observed_at=now, road_id="HN-1")
    quality.observe(status="invalid")
    quality.observe(status="late")
    snapshot = quality.snapshot(now)
    assert snapshot.events_received == 4
    assert snapshot.invalid_rate == 0.25
    assert snapshot.duplicate_rate == 0.25
    assert snapshot.late_events == 1
    assert snapshot.roads_reporting == 1
    assert snapshot.freshness_p95_seconds == 20
