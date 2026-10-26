from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from cognitive_traffic.contracts.events import EventMetadata, utc


class TrafficFeatures(EventMetadata):
    road_id: str
    city: str
    prediction_time: datetime
    feature_version: str
    speed_kmh: float = Field(ge=0)
    speed_mean_15m: float | None = None
    speed_mean_30m: float | None = None
    speed_mean_60m: float | None = None
    speed_std_60m: float | None = Field(default=None, ge=0)
    speed_change_kmh: float | None = None
    precipitation_mm: float | None = Field(default=None, ge=0)
    event_severity: int = Field(default=0, ge=0, le=3)
    neighbor_mean_speed_kmh: float | None = Field(default=None, ge=0)

    @field_validator("prediction_time")
    @classmethod
    def require_prediction_timezone(cls, value: datetime) -> datetime:
        return utc(value)


class Forecast(EventMetadata):
    road_id: str
    city: str
    prediction_time: datetime
    target_time: datetime
    horizon_minutes: int = Field(gt=0)
    model_version: str
    feature_version: str
    p10_speed_kmh: float = Field(ge=0)
    p50_speed_kmh: float = Field(ge=0)
    p90_speed_kmh: float = Field(ge=0)

    @field_validator("prediction_time", "target_time")
    @classmethod
    def require_forecast_timezone(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def validate_quantiles_and_times(self) -> Forecast:
        if not self.p10_speed_kmh <= self.p50_speed_kmh <= self.p90_speed_kmh:
            raise ValueError("forecast quantiles must satisfy p10 <= p50 <= p90")
        if self.target_time <= self.prediction_time:
            raise ValueError("target_time must follow prediction_time")
        return self


class PredictionOutcome(EventMetadata):
    road_id: str
    model_version: str
    prediction_id: str
    prediction_time: datetime
    target_time: datetime
    forecast_speed_kmh: float = Field(ge=0)
    actual_speed_kmh: float = Field(ge=0)
    absolute_error_kmh: float = Field(ge=0)

    @field_validator("prediction_time", "target_time")
    @classmethod
    def require_outcome_timezone(cls, value: datetime) -> datetime:
        return utc(value)
