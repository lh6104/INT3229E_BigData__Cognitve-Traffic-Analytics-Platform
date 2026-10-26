from datetime import UTC, datetime

from cognitive_traffic.ingestion.weather import source_event as weather_source_event
from cognitive_traffic.streaming.processors import dead_letter_for, normalize_weather

NOW = datetime(2026, 8, 12, tzinfo=UTC)


def test_source_weather_units_and_canonical_adapter_are_consistent() -> None:
    raw = weather_source_event(
        {"weather_cell_id": "HN-W-1", "city": "hanoi"},
        {"main": {"temp": 31}, "wind": {"speed": 2}, "rain": {"1h": 3}, "weather": [{"main": "Rain"}]},
        NOW,
    )
    canonical = normalize_weather(raw)
    assert canonical.wind_speed_kmh == 7.2
    assert canonical.precipitation_mm == 3


def test_invalid_source_event_has_replayable_dead_letter() -> None:
    payload = {"road_id": "HN-1", "speed_kmh": -1}
    first = dead_letter_for(original_topic="traffic.raw.v1", payload=payload, error=ValueError("bad speed"))
    second = dead_letter_for(original_topic="traffic.raw.v1", payload=payload, error=ValueError("bad speed"))
    assert first.event_id == second.event_id
    assert first.original_topic == "traffic.raw.v1"
