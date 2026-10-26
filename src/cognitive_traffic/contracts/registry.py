"""Contracts for configured monitoring points and dataset identities."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MonitoringPoint(BaseModel):
    """A configured monitoring anchor, not a verified road/provider mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    point_id: str = Field(alias="segment_id", min_length=1)
    city: Literal["hanoi", "hcmc"]
    weather_cell_id: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)


class DatasetProfile(BaseModel):
    """Declared dataset semantics and acquisition/rights evidence status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(min_length=1)
    profile_version: Literal["1"]
    purpose: Literal["operational", "benchmark"]
    measurement: Literal["speed", "flow", "video"]
    unit: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    acquisition_status: Literal["configured_unverified", "not_acquired"]
    rights_status: Literal["unverified"]

    @model_validator(mode="after")
    def validate_measurement_unit(self) -> "DatasetProfile":
        permitted_units = {
            "speed": {"km/h", "mph"},
            "flow": {"source_units_unverified"},
            "video": {"frame"},
        }
        if self.unit not in permitted_units[self.measurement]:
            raise ValueError("measurement/unit mismatch")
        return self
