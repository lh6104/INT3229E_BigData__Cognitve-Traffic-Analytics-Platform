"""Versioned messages exchanged by the traffic platform."""

from cognitive_traffic.contracts.events import DeadLetterEvent, RoadEvent, RoadEventType, deterministic_event_id
from cognitive_traffic.contracts.forecasts import Forecast, PredictionOutcome, TrafficFeatures
from cognitive_traffic.contracts.traffic import TrafficObservation
from cognitive_traffic.contracts.weather import WeatherObservation

__all__ = [
    "DeadLetterEvent",
    "Forecast",
    "PredictionOutcome",
    "RoadEvent",
    "RoadEventType",
    "TrafficFeatures",
    "TrafficObservation",
    "WeatherObservation",
    "deterministic_event_id",
]
