from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, field_validator, model_validator

from cognitive_traffic.contracts.events import EventMetadata, deterministic_event_id


class TrafficObservation(EventMetadata):
    road_id: str
    city: str
    speed_kmh: float = Field(ge=0, le=180)
    free_flow_speed_kmh: float = Field(gt=0, le=200)
    confidence: float = Field(default=1.0, ge=0, le=1)
    available_at: datetime

    @field_validator("available_at")
    @classmethod
    def require_available_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("available_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_availability(self) -> TrafficObservation:
        if self.available_at < self.event_time:
            raise ValueError("available_at cannot precede event_time")
        return self

    @classmethod
    def create(
        cls,
        *,
        road_id: str,
        city: str,
        event_time: datetime,
        ingested_at: datetime,
        speed_kmh: float,
        free_flow_speed_kmh: float,
        source: str,
        source_record_id: str = "",
        confidence: float = 1.0,
        available_at: datetime | None = None,
    ) -> TrafficObservation:
        return cls(
            event_id=deterministic_event_id(
                source=source,
                entity_id=road_id,
                event_time=event_time,
                source_record_id=source_record_id,
            ),
            road_id=road_id,
            city=city,
            event_time=event_time,
            ingested_at=ingested_at,
            available_at=available_at or ingested_at,
            speed_kmh=speed_kmh,
            free_flow_speed_kmh=free_flow_speed_kmh,
            confidence=confidence,
            source=source,
            source_record_id=source_record_id,
        )
