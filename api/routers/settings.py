"""Application settings endpoints backed by local JSON persistence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services.local_data import DATA_DIR, PROJECT_ROOT, DataUnavailableError, latest_by_segment, normalize_city, traffic_features

logger = logging.getLogger(__name__)

router = APIRouter()

SETTINGS_PATH = DATA_DIR / "app_settings.json"


class CityRuntime(BaseModel):
    enabled: bool
    status: Literal["online", "offline"]
    segment_count: int
    latest_timestamp: datetime | None = None
    avg_speed: float | None = None
    avg_jam_factor: float | None = None


class AlertThresholds(BaseModel):
    critical_jam_factor: float = Field(6.0, ge=0.0, le=10.0)
    high_jam_factor: float = Field(4.0, ge=0.0, le=10.0)
    medium_jam_factor: float = Field(3.0, ge=0.0, le=10.0)


class RefreshIntervals(BaseModel):
    traffic_seconds: int = Field(60, ge=5, le=3600)
    weather_seconds: int = Field(300, ge=30, le=3600)
    alerts_seconds: int = Field(30, ge=5, le=3600)
    monitoring_seconds: int = Field(30, ge=5, le=3600)


class MapSettings(BaseModel):
    default_city: Literal["hanoi", "hcmc"] = "hanoi"
    zoom_level: int = Field(13, ge=8, le=18)


class AppSettings(BaseModel):
    city_toggles: Dict[str, bool] = {"hanoi": True, "hcmc": True}
    thresholds: AlertThresholds = AlertThresholds()
    intervals: RefreshIntervals = RefreshIntervals()
    map: MapSettings = MapSettings()
    updated_at: datetime | None = None


class AppSettingsResponse(AppSettings):
    cities: Dict[str, CityRuntime]
    storage_path: str


def _default_settings() -> AppSettings:
    return AppSettings(updated_at=datetime.now(timezone.utc))


def _read_settings() -> AppSettings:
    if not SETTINGS_PATH.exists():
        return _default_settings()
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return AppSettings.model_validate(payload)
    except Exception as exc:
        logger.exception("Could not read settings file %s", SETTINGS_PATH)
        raise HTTPException(status_code=500, detail=f"Could not read settings: {exc}") from exc


def _write_settings(settings: AppSettings) -> AppSettings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.updated_at = datetime.now(timezone.utc)
    SETTINGS_PATH.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    return settings


def _runtime_city_state(settings: AppSettings) -> Dict[str, CityRuntime]:
    cities = ["hanoi", "hcmc"]
    runtime: Dict[str, CityRuntime] = {}
    try:
        all_latest = latest_by_segment(traffic_features())
    except DataUnavailableError:
        all_latest = None

    for city in cities:
        enabled = bool(settings.city_toggles.get(city, True))
        rows = all_latest[all_latest["city"].map(normalize_city) == city] if all_latest is not None and "city" in all_latest else None
        if rows is None or rows.empty:
            runtime[city] = CityRuntime(enabled=enabled, status="offline", segment_count=0)
            continue
        runtime[city] = CityRuntime(
            enabled=enabled,
            status="online" if enabled else "offline",
            segment_count=int(rows["segment_id"].nunique()),
            latest_timestamp=rows["timestamp"].max().to_pydatetime(),
            avg_speed=round(float(rows["currentSpeed"].mean()), 2),
            avg_jam_factor=round(float(rows["jamFactor"].mean()), 2),
        )
    return runtime


def _response(settings: AppSettings) -> AppSettingsResponse:
    return AppSettingsResponse(
        **settings.model_dump(),
        cities=_runtime_city_state(settings),
        storage_path=str(SETTINGS_PATH.relative_to(PROJECT_ROOT)),
    )


@router.get("", response_model=AppSettingsResponse)
def get_settings():
    """Get persisted app settings plus current city runtime state."""
    return _response(_read_settings())


@router.put("", response_model=AppSettingsResponse)
def update_settings(settings: AppSettings):
    """Persist app settings to the local data directory."""
    known_cities = {"hanoi", "hcmc"}
    unknown = set(settings.city_toggles) - known_cities
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown city toggle(s): {', '.join(sorted(unknown))}")
    if settings.thresholds.critical_jam_factor < settings.thresholds.high_jam_factor:
        raise HTTPException(status_code=400, detail="Critical jam threshold must be >= high threshold")
    if settings.thresholds.high_jam_factor < settings.thresholds.medium_jam_factor:
        raise HTTPException(status_code=400, detail="High jam threshold must be >= medium threshold")
    saved = _write_settings(settings)
    logger.info("Settings persisted to %s", SETTINGS_PATH)
    return _response(saved)
