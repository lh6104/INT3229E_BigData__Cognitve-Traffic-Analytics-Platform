from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from cognitive_traffic.contracts.traffic import TrafficObservation


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

    def store_observation(self, event: TrafficObservation) -> str:
        """Commit immutable history and monotonic live state in one transaction.

        Kafka offsets are acknowledged only after this transaction succeeds.
        Revalidate even model_copy/model_construct callers at the trust boundary.
        """
        from psycopg.types.json import Jsonb

        event = TrafficObservation.model_validate(event.model_dump())
        now = datetime.now(UTC)
        if event.mode != "operational" or event.dataset_id != "vn-mvp-12":
            raise ValueError("only the operational vn-mvp-12 dataset may enter live serving")
        if max(event.event_time, event.available_at, event.ingested_at) > now:
            raise ValueError("future observation timestamp")
        payload = event.model_dump(mode="json")
        with self.connection() as connection:
            road = connection.execute(
                "SELECT city FROM roads WHERE road_id=%s AND monitoring_enabled", (event.road_id,)
            ).fetchone()
            if road is None or road["city"] != event.city:
                raise ValueError("unknown monitoring point or wrong city")
            inserted = connection.execute(
                """INSERT INTO traffic_observations
                (event_id, road_id, city, event_time, ingested_at, speed_kmh,
                 free_flow_speed_kmh, confidence, source, schema_version,
                 dataset_id, mode, canonical_payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING RETURNING event_id""",
                (event.event_id, event.road_id, event.city, event.event_time, event.ingested_at,
                 event.speed_kmh, event.free_flow_speed_kmh, event.confidence, event.source,
                 event.schema_version, event.dataset_id, event.mode, Jsonb(payload)),
            ).fetchone()
            if inserted is None:
                rows = connection.execute(
                    "SELECT event_id, canonical_payload FROM traffic_observations WHERE event_id=%s",
                    (event.event_id,),
                ).fetchall()
                if len(rows) == 1 and rows[0]["canonical_payload"] == payload:
                    return "duplicate"
                raise ValueError("event identity collision or inconsistent payload")
            connection.execute(
                """INSERT INTO traffic_current
                  (road_id, city, event_time, speed_kmh, free_flow_speed_kmh,
                   confidence, source, event_id, dataset_id, mode)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                  ON CONFLICT (road_id) DO UPDATE SET
                    city=EXCLUDED.city, event_time=EXCLUDED.event_time,
                    speed_kmh=EXCLUDED.speed_kmh, free_flow_speed_kmh=EXCLUDED.free_flow_speed_kmh,
                    confidence=EXCLUDED.confidence, source=EXCLUDED.source,
                    event_id=EXCLUDED.event_id, dataset_id=EXCLUDED.dataset_id, mode=EXCLUDED.mode
                  WHERE (EXCLUDED.event_time, EXCLUDED.event_id) >
                        (traffic_current.event_time, COALESCE(traffic_current.event_id, ''))""",
                (event.road_id, event.city, event.event_time, event.speed_kmh,
                 event.free_flow_speed_kmh, event.confidence, event.source,
                 event.event_id, event.dataset_id, event.mode),
            )
        return "accepted"

    def monitoring_points(self, city: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """SELECT roads.road_id, roads.city, roads.name, roads.category, roads.geometry,
                roads.anchor_lat AS latitude, roads.anchor_lon AS longitude,
                'configured_anchor' AS coordinate_kind,
                current.event_time, current.speed_kmh, current.free_flow_speed_kmh,
                current.confidence, current.source, current.dataset_id, current.mode,
                CASE WHEN current.event_time IS NULL THEN 'missing'
                     WHEN current.event_time < now() - interval '10 minutes' THEN 'stale'
                     ELSE 'live' END AS status
            FROM roads LEFT JOIN traffic_current AS current ON roads.road_id=current.road_id
                AND current.mode='operational' AND current.dataset_id='vn-mvp-12'
            WHERE roads.monitoring_enabled AND (%s::text IS NULL OR roads.city=%s)
            ORDER BY roads.road_id""", (city, city),
        )

    def roads(self, city: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            "SELECT road_id, city, name, category FROM roads WHERE (%s::text IS NULL OR city = %s) ORDER BY road_id",
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
            WHERE roads.monitoring_enabled
              AND current.mode = 'operational' AND current.dataset_id = 'vn-mvp-12'
              AND (%s::text IS NULL OR current.city = %s)
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
            WHERE (%s::text IS NULL OR forecast.road_id = %s)
              AND (%s::integer IS NULL OR forecast.horizon_minutes = %s)
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
            WHERE (%s::text IS NULL OR city = %s)
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
