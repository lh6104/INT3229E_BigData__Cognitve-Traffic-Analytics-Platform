"""One source of truth for topic names and partition keys."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicSpec:
    name: str
    key_field: str
    partitions: int = 6


TRAFFIC_RAW = TopicSpec("traffic.raw.v1", "road_id")
WEATHER_RAW = TopicSpec("weather.raw.v1", "weather_cell_id")
NEWS_RAW = TopicSpec("news.raw.v1", "source_record_id")
TRAFFIC_OBSERVATIONS = TopicSpec("traffic.observation.v1", "road_id")
WEATHER_OBSERVATIONS = TopicSpec("weather.observation.v1", "weather_cell_id")
ROAD_EVENTS = TopicSpec("road.event.v1", "road_id")
TRAFFIC_FEATURES = TopicSpec("traffic.features.v1", "road_id")
TRAFFIC_FORECASTS = TopicSpec("traffic.forecasts.v1", "road_id")
TRAFFIC_ALERTS = TopicSpec("traffic.alerts.v1", "road_id")
PREDICTION_OUTCOMES = TopicSpec("prediction.outcomes.v1", "road_id")
DEAD_LETTER = TopicSpec("dead_letter.v1", "event_id", partitions=3)

ALL_TOPICS = (
    TRAFFIC_RAW,
    WEATHER_RAW,
    NEWS_RAW,
    TRAFFIC_OBSERVATIONS,
    WEATHER_OBSERVATIONS,
    ROAD_EVENTS,
    TRAFFIC_FEATURES,
    TRAFFIC_FORECASTS,
    TRAFFIC_ALERTS,
    PREDICTION_OUTCOMES,
    DEAD_LETTER,
)
