from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from cognitive_traffic.contracts.events import EventMetadata, deterministic_event_id, utc


class WeatherObservation(EventMetadata):
    weather_cell_id: str
    city: str
    temperature_c: float = Field(ge=-80, le=70)
    precipitation_mm: float = Field(default=0, ge=0)
    wind_speed_kmh: float = Field(default=0, ge=0, le=450)
    condition: str = "unknown"
    available_at: datetime

    @field_validator("available_at")
    @classmethod
    def require_available_at_timezone(cls, value: datetime) -> datetime:
        return utc(value)

    @classmethod
    def create(
        cls,
        *,
        weather_cell_id: str,
        city: str,
        event_time: datetime,
        ingested_at: datetime,
        source: str,
        temperature_c: float,
        precipitation_mm: float = 0,
        wind_speed_kmh: float = 0,
        condition: str = "unknown",
        source_record_id: str = "",
        available_at: datetime | None = None,
    ) -> WeatherObservation:
        return cls(
            event_id=deterministic_event_id(
                source=source,
                entity_id=weather_cell_id,
                event_time=event_time,
                source_record_id=source_record_id,
            ),
            weather_cell_id=weather_cell_id,
            city=city,
            event_time=event_time,
            ingested_at=ingested_at,
            available_at=available_at or ingested_at,
            source=source,
            source_record_id=source_record_id,
            temperature_c=temperature_c,
            precipitation_mm=precipitation_mm,
            wind_speed_kmh=wind_speed_kmh,
            condition=condition,
        )
