from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


def deterministic_event_id(
    *, source: str, entity_id: str, event_time: datetime, source_record_id: str = ""
) -> str:
    timestamp = utc(event_time).isoformat(timespec="microseconds")
    material = "\x1f".join((source.strip().lower(), entity_id, timestamp, source_record_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class EventContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EventMetadata(EventContract):
    event_id: str
    event_time: datetime
    ingested_at: datetime
    source: str
    source_record_id: str = ""
    schema_version: str = SCHEMA_VERSION

    @field_validator("event_time", "ingested_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        return utc(value)

    @field_validator("event_id", "source")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value


class DeadLetterEvent(EventContract):
    original_topic: str
    event_id: str | None = None
    failure_reason: str
    failed_at: datetime
    payload: dict[str, Any]
    payload_reference: str | None = None

    @field_validator("failed_at")
    @classmethod
    def require_failed_at_timezone(cls, value: datetime) -> datetime:
        return utc(value)


class RoadEventType(StrEnum):
    ACCIDENT = "accident"
    FLOOD = "flood"
    ROAD_WORK = "road_work"
    CLOSURE = "closure"
    PUBLIC_EVENT = "public_event"
    OTHER = "other"


class RoadEvent(EventMetadata):
    road_id: str
    city: str
    event_type: RoadEventType
    severity: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0, le=1)
    available_at: datetime
    expires_at: datetime | None = None

    @field_validator("available_at", "expires_at")
    @classmethod
    def require_context_timestamp_timezone(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @classmethod
    def create(
        cls,
        *,
        road_id: str,
        city: str,
        event_type: RoadEventType,
        severity: int,
        confidence: float,
        event_time: datetime,
        ingested_at: datetime,
        source: str,
        source_record_id: str = "",
        available_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> RoadEvent:
        return cls(
            event_id=deterministic_event_id(
                source=source,
                entity_id=road_id,
                event_time=event_time,
                source_record_id=source_record_id,
            ),
            road_id=road_id,
            city=city,
            event_type=event_type,
            severity=severity,
            confidence=confidence,
            event_time=event_time,
            ingested_at=ingested_at,
            available_at=available_at or ingested_at,
            expires_at=expires_at,
            source=source,
            source_record_id=source_record_id,
        )
