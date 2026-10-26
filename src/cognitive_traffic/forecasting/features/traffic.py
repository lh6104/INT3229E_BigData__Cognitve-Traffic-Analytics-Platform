"""Feature implementation shared by replay/training and online processing."""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cognitive_traffic.contracts.events import RoadEvent, deterministic_event_id
from cognitive_traffic.contracts.forecasts import TrafficFeatures
from cognitive_traffic.contracts.traffic import TrafficObservation
from cognitive_traffic.contracts.weather import WeatherObservation
from cognitive_traffic.forecasting.features.spatial import latest_neighbor_mean


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    version: str
    source: str
    lookback_minutes: int
    required_fields: tuple[str, ...]
    availability_rule: str = "available_at <= prediction_time"


FEATURE_REGISTRY: dict[str, FeatureDefinition] = {
    item.name: item
    for item in (
        FeatureDefinition("speed_kmh", "1", "traffic", 0, ("speed_kmh",)),
        FeatureDefinition("speed_mean_15m", "1", "traffic", 15, ("speed_kmh", "event_time")),
        FeatureDefinition("speed_mean_30m", "1", "traffic", 30, ("speed_kmh", "event_time")),
        FeatureDefinition("speed_mean_60m", "1", "traffic", 60, ("speed_kmh", "event_time")),
        FeatureDefinition("speed_std_60m", "1", "traffic", 60, ("speed_kmh", "event_time")),
        FeatureDefinition("speed_change_kmh", "1", "traffic", 60, ("speed_kmh", "event_time")),
        FeatureDefinition("precipitation_mm", "1", "weather", 180, ("precipitation_mm", "available_at")),
        FeatureDefinition("event_severity", "1", "road_event", 180, ("severity", "available_at")),
        FeatureDefinition("neighbor_mean_speed_kmh", "1", "traffic", 15, ("speed_kmh", "road_id")),
    )
}


def target_time(prediction_time: datetime, horizon_minutes: int) -> datetime:
    if horizon_minutes <= 0:
        raise ValueError("horizon_minutes must be positive")
    return prediction_time + timedelta(minutes=horizon_minutes)


def assert_point_in_time_correct(
    *, prediction_time: datetime, feature_available_at: Iterable[datetime], target_at: datetime
) -> None:
    unavailable = [value for value in feature_available_at if value > prediction_time]
    if unavailable:
        raise ValueError(f"{len(unavailable)} feature values were unavailable at prediction_time")
    if target_at <= prediction_time:
        raise ValueError("target timestamp must be after prediction_time")


def _visible(record: object, prediction_time: datetime) -> bool:
    event_time = record.event_time
    available_at = getattr(record, "available_at", record.ingested_at)
    return event_time <= prediction_time and available_at <= prediction_time


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


class PointInTimeFeatureBuilder:
    def __init__(self, feature_version: str = "1") -> None:
        self.feature_version = feature_version

    def build(
        self,
        *,
        road_id: str,
        city: str,
        prediction_time: datetime,
        traffic: Iterable[TrafficObservation],
        weather: Iterable[WeatherObservation] = (),
        events: Iterable[RoadEvent] = (),
        neighbor_road_ids: set[str] | None = None,
    ) -> TrafficFeatures:
        if prediction_time.tzinfo is None:
            raise ValueError("prediction_time must include a timezone")
        prediction_time = prediction_time.astimezone(UTC)
        visible_traffic = sorted(
            (
                item
                for item in traffic
                if _visible(item, prediction_time)
                and item.event_time >= prediction_time - timedelta(minutes=60)
            ),
            key=lambda item: item.event_time,
        )
        road_history = [item for item in visible_traffic if item.road_id == road_id]
        if not road_history:
            raise ValueError(f"no point-in-time traffic observations for road {road_id}")
        latest = road_history[-1]

        def speeds(minutes: int) -> list[float]:
            cutoff = prediction_time - timedelta(minutes=minutes)
            return [item.speed_kmh for item in road_history if item.event_time >= cutoff]

        values_60m = speeds(60)
        weather_state = [item for item in weather if item.city == city and _visible(item, prediction_time)]
        latest_weather = max(weather_state, key=lambda item: item.event_time, default=None)
        event_state = [
            item
            for item in events
            if item.road_id == road_id
            and _visible(item, prediction_time)
            and (item.expires_at is None or item.expires_at > prediction_time)
        ]
        severity = max((item.severity for item in event_state), default=0)
        neighbor_mean = latest_neighbor_mean(visible_traffic, neighbor_road_ids or set())

        event_id = deterministic_event_id(
            source="feature-builder",
            entity_id=road_id,
            event_time=prediction_time,
            source_record_id=self.feature_version,
        )
        return TrafficFeatures(
            event_id=event_id,
            event_time=prediction_time,
            ingested_at=prediction_time,
            source="feature-builder",
            source_record_id=latest.event_id,
            road_id=road_id,
            city=city,
            prediction_time=prediction_time,
            feature_version=self.feature_version,
            speed_kmh=latest.speed_kmh,
            speed_mean_15m=_mean(speeds(15)),
            speed_mean_30m=_mean(speeds(30)),
            speed_mean_60m=_mean(values_60m),
            speed_std_60m=statistics.pstdev(values_60m) if len(values_60m) > 1 else 0.0,
            speed_change_kmh=latest.speed_kmh - values_60m[0] if values_60m else None,
            precipitation_mm=latest_weather.precipitation_mm if latest_weather else None,
            event_severity=severity,
            neighbor_mean_speed_kmh=neighbor_mean,
        )
