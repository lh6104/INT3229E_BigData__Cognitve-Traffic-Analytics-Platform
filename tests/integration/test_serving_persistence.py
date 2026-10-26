"""Real PostgreSQL serving invariants; set TRAFFIC_TEST_DSN to an isolated test DB."""
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from cognitive_traffic.contracts.traffic import TrafficObservation
from cognitive_traffic.storage.postgres import TrafficRepository


@pytest.fixture
def repo():
    dsn = os.getenv('TRAFFIC_TEST_DSN')
    if not dsn:
        pytest.skip('TRAFFIC_TEST_DSN is required for real PostgreSQL acceptance')
    import psycopg
    from psycopg.conninfo import make_conninfo

    from cognitive_traffic.storage.bootstrap import bootstrap
    schema = 'test_serving_' + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA {schema}')
    scoped = make_conninfo(dsn, options=f'-c search_path={schema}')
    bootstrap(scoped)
    bootstrap(scoped)  # existing-volume rerun
    yield TrafficRepository(scoped)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA {schema} CASCADE')


def observation(**changes):
    now = datetime.now(UTC) - timedelta(seconds=1)
    fields = dict(road_id='HN_HK_001', city='hanoi', event_time=now,
                  ingested_at=now, speed_kmh=30, free_flow_speed_kmh=50,
                  source='acceptance-fixture', mode='operational', dataset_id='vn-mvp-12')
    fields.update(changes)
    return TrafficObservation.create(**fields)


def test_registry_empty_and_transactional_idempotent_monotonic_current(repo):
    points = repo.monitoring_points(None)
    assert len(points) == 12
    assert all(p['status'] == 'missing' and p['geometry'] is None for p in points)
    event = observation()
    assert repo.store_observation(event) == 'accepted'
    assert repo.store_observation(event) == 'duplicate'
    assert repo.store_observation(observation(event_time=event.event_time-timedelta(minutes=1))) == 'accepted'
    assert repo.current_traffic('hanoi')[0]['event_time'] == event.event_time
    assert len(repo.traffic_history(event.road_id, 100)) == 2
    assert repo.monitoring_points('hanoi')[0]['coordinate_kind'] == 'configured_anchor'
    changed = event.model_copy(update={'speed_kmh': 99})
    with pytest.raises(ValueError, match='collision'):
        repo.store_observation(changed)
    assert repo.current_traffic('hanoi')[0]['speed_kmh'] == 30
    other_id = event.model_copy(update={'event_id': 'conflicting-natural-key'})
    with pytest.raises(ValueError, match='collision'):
        repo.store_observation(other_id)
    assert len(repo.traffic_history(event.road_id, 100)) == 2


@pytest.mark.parametrize('changes', [
    {'mode': 'replay'}, {'mode': 'benchmark'}, {'dataset_id': 'metr-la'},
    {'mode': 'unspecified'}, {'road_id': 'unknown'}, {'city': 'hcmc'},
    {'event_time': datetime.now(UTC)+timedelta(days=1), 'ingested_at': datetime.now(UTC)+timedelta(days=1)},
    {'ingested_at': datetime.now(UTC)+timedelta(days=1)},
])
def test_sink_rejects_nonoperational_unknown_wrongcity_and_future(repo, changes):
    with pytest.raises(ValueError):
        repo.store_observation(observation(**changes))
    assert repo.current_traffic(None) == []


def test_sink_revalidates_bypassed_contract_and_marks_old_readings_stale(repo):
    event = observation(event_time=datetime.now(UTC)-timedelta(hours=1))
    with pytest.raises(ValueError):
        repo.store_observation(event.model_copy(update={'speed_kmh': float('nan')}))
    repo.store_observation(event)
    point = next(p for p in repo.monitoring_points(None) if p['road_id'] == event.road_id)
    assert point['status'] == 'stale'


def test_current_failure_rolls_back_history_and_retry_is_safe(repo):
    import psycopg
    event = observation()
    with repo.connection() as conn:
        conn.execute('''CREATE FUNCTION reject_current() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'injected crash before current write'; END $$''')
        conn.execute('''CREATE TRIGGER crash_current BEFORE INSERT ON traffic_current
                        FOR EACH ROW EXECUTE FUNCTION reject_current()''')
    with pytest.raises(psycopg.Error, match='injected crash'):
        repo.store_observation(event)
    assert repo.traffic_history(event.road_id, 100) == []
    with repo.connection() as conn:
        conn.execute('DROP TRIGGER crash_current ON traffic_current')
    assert repo.store_observation(event) == 'accepted'
    assert repo.store_observation(event) == 'duplicate'


def test_concurrent_deliveries_advance_current_without_duplicate_history(repo):
    from concurrent.futures import ThreadPoolExecutor
    event = observation()
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(repo.store_observation, [event] * 4))
    assert sorted(statuses) == ['accepted', 'duplicate', 'duplicate', 'duplicate']
    assert len(repo.traffic_history(event.road_id, 100)) == 1


def test_current_read_excludes_disabled_roads_and_ineligible_existing_rows(repo):
    """An existing volume may contain prior anchors or unverified provenance."""
    event = observation()
    repo.store_observation(event)
    with repo.connection() as conn:
        conn.execute("UPDATE roads SET monitoring_enabled=false WHERE road_id=%s", (event.road_id,))
    assert repo.current_traffic(None) == []
    assert len(repo.traffic_history(event.road_id, 10)) == 1  # Preserve history for auditing.
    with repo.connection() as conn:
        conn.execute("UPDATE roads SET monitoring_enabled=true WHERE road_id=%s", (event.road_id,))
    assert len(repo.current_traffic(None)) == 1
    for field, invalid in [('mode', 'replay'), ('dataset_id', 'metr-la'), ('dataset_id', None)]:
        with repo.connection() as conn:
            # Field names are a fixed test-owned allowlist, values stay parameterized.
            conn.execute(f"UPDATE traffic_current SET {field}=%s WHERE road_id=%s", (invalid, event.road_id))
        assert repo.current_traffic(None) == []
        with repo.connection() as conn:
            conn.execute("UPDATE traffic_current SET mode='operational', dataset_id='vn-mvp-12'")
    assert len(repo.current_traffic('hanoi')) == 1
    assert repo.current_traffic('hcmc') == []
