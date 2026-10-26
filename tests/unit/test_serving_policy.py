from datetime import UTC, datetime


def test_replay_strips_operational_mode_before_normalization():
    from cognitive_traffic.streaming.processors import normalize_traffic
    from cognitive_traffic.streaming.replay import replay_payload
    now = datetime.now(UTC).isoformat()
    original = dict(road_id='HN_HK_001', city='hanoi', event_time=now, ingested_at=now,
                    speed_kmh=30, free_flow_speed_kmh=50, source='tomtom',
                    dataset_id='vn-mvp-12', mode='operational')
    result = replay_payload(original)
    assert original['mode'] == 'operational'
    assert normalize_traffic(result).mode == 'replay'
    assert normalize_traffic(result).dataset_id == 'vn-mvp-12'
