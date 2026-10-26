from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class TrafficRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg

        with psycopg.connect(self.dsn, connect_timeout=2, row_factory=psycopg.rows.dict_row) as connection:
            yield connection

    def fetch_all(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return list(cursor.fetchall())

    def roads(self, city: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            "SELECT road_id, city, name, category FROM roads WHERE (%s IS NULL OR city = %s) ORDER BY road_id",
            (city, city),
        )

    def current_traffic(self, city: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT current.road_id, current.city, roads.name, roads.category,
                   roads.geometry, current.event_time, current.speed_kmh,
                   current.free_flow_speed_kmh, current.confidence, current.source
            FROM traffic_current AS current
            JOIN roads USING (road_id)
            WHERE (%s IS NULL OR current.city = %s)
            ORDER BY current.road_id
            """,
            (city, city),
        )

    def traffic_history(self, road_id: str, limit: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT road_id, event_time, speed_kmh, free_flow_speed_kmh, confidence
            FROM traffic_observations WHERE road_id = %s
            ORDER BY event_time DESC LIMIT %s
            """,
            (road_id, limit),
        )

    def forecasts(self, road_id: str | None, horizon: int | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT forecast.event_id, forecast.road_id, forecast.city,
                   forecast.prediction_time, forecast.target_time,
                   forecast.horizon_minutes, forecast.model_version,
                   forecast.p10_speed_kmh, forecast.p50_speed_kmh,
                   forecast.p90_speed_kmh, outcome.actual_speed_kmh,
                   outcome.absolute_error_kmh
            FROM forecasts AS forecast
            LEFT JOIN prediction_outcomes AS outcome
              ON outcome.prediction_id = forecast.event_id
            WHERE (%s IS NULL OR forecast.road_id = %s)
              AND (%s IS NULL OR forecast.horizon_minutes = %s)
            ORDER BY forecast.prediction_time DESC LIMIT 500
            """,
            (road_id, road_id, horizon, horizon),
        )

    def hotspots(self, city: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT road_id, city, target_time, p50_speed_kmh,
                   congestion_probability, model_version
            FROM forecast_hotspots
            WHERE (%s IS NULL OR city = %s)
            ORDER BY congestion_probability DESC LIMIT 50
            """,
            (city, city),
        )

    def alerts(self, active_only: bool) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT alert_id, road_id, created_at, alert_type, severity, status, reason
            FROM alerts WHERE (NOT %s OR status = 'active')
            ORDER BY created_at DESC LIMIT 200
            """,
            (active_only,),
        )

    def current_model(self) -> dict[str, Any] | None:
        rows = self.fetch_all(
            """
            SELECT model_name, model_version, stage, dataset_id, feature_version,
                   git_sha, promoted_at
            FROM model_versions WHERE stage = 'champion'
            ORDER BY promoted_at DESC LIMIT 1
            """
        )
        return rows[0] if rows else None

    def model_metrics(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT model_version, horizon_minutes, window_start, window_end,
                   sample_count, mae, rmse, bias
            FROM model_performance ORDER BY window_end DESC, horizon_minutes LIMIT 100
            """
        )

    def data_quality(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT measured_at, stream, events_received, invalid_events, duplicates,
                   late_events, freshness_p95_seconds, roads_reporting, expected_roads
            FROM data_quality_metrics ORDER BY measured_at DESC LIMIT 100
            """
        )

    def ping(self) -> bool:
        return bool(self.fetch_all("SELECT 1 AS ok"))
