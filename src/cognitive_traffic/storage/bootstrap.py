"""Idempotent schema migration and configured monitoring-anchor registration."""
from pathlib import Path

from cognitive_traffic.monitoring.registry import load_monitoring_points
from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.postgres import TrafficRepository


def bootstrap(dsn: str, root: Path = Path('.')) -> None:
    # Validate the approved identities, cities and coordinate bounds before any DDL.
    points = load_monitoring_points(root / 'configs/sources.yaml')
    repository = TrafficRepository(dsn)
    with repository.connection() as connection:
        # Serialize concurrent bootstrap containers, including on existing volumes.
        connection.execute("SELECT pg_advisory_xact_lock(7210381)")
        connection.execute((root / 'infra/postgres/schema.sql').read_text())
        for migration in sorted((root / 'infra/postgres/migrations').glob('*.sql')):
            connection.execute(migration.read_text())
        connection.execute('UPDATE roads SET monitoring_enabled = false')
        for point in points:
            connection.execute('''
                INSERT INTO roads (road_id, city, name, category, anchor_lat, anchor_lon, monitoring_enabled)
                VALUES (%s, %s, %s, 'monitoring_anchor', %s, %s, true)
                ON CONFLICT (road_id) DO UPDATE SET city=EXCLUDED.city,
                  anchor_lat=EXCLUDED.anchor_lat, anchor_lon=EXCLUDED.anchor_lon, monitoring_enabled=true
            ''', (point.point_id, point.city, point.point_id, point.lat, point.lon))


if __name__ == '__main__':
    bootstrap(get_settings().postgres_dsn)
