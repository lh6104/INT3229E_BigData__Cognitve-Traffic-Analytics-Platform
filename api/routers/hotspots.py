"""Congestion hotspot endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, List, Optional
from datetime import datetime
import logging

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, traffic_features
from api.services.model_inference import ModelUnavailableError, normalize_horizon, predict_for_segment

logger = logging.getLogger(__name__)

router = APIRouter()


class Hotspot(BaseModel):
    """Congestion hotspot cluster."""
    hotspot_id: str
    cluster_id: int
    city: str
    center_lat: float
    center_lon: float
    radius_km: float
    num_segments: int
    avg_congestion: float
    avg_jam_factor: float
    severity: str  # low, medium, high
    detected_at: datetime


class PredictedHotspot(BaseModel):
    """Segment-level predicted congestion risk."""
    segment_id: str
    road_name: str
    city: str
    current_speed: float
    predicted_speed: float
    free_flow_speed: float
    horizon: str
    risk_level: str
    reason: str
    latest_timestamp: Optional[str] = None
    geometry: Optional[Any] = None
    model_name: str
    filled_feature_count: int
    is_fallback: bool


@router.get("", response_model=List[Hotspot])
def get_hotspots(
    city: str = Query("hanoi", description="Filter by city"),
    severity: str = Query(None, description="Filter by severity (low, medium, high)")
):
    """Get current congestion hotspots.

    Args:
        city: City code
        severity: Optional severity filter

    Returns:
        List of detected hotspot clusters
    """
    city = normalize_city(city)
    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        return []

    congested = latest[latest["jamFactor"] >= 3].copy()
    if congested.empty:
        return []

    congested["cluster_id"] = congested["segment_name"].fillna(congested["segment_id"]).astype(str).str[:12]
    hotspots = []
    for idx, (_, group) in enumerate(congested.groupby("cluster_id")):
        avg_jam = float(group["jamFactor"].mean())
        sev = "critical" if avg_jam >= 8 else "high" if avg_jam >= 6 else "medium"
        hotspots.append(
            Hotspot(
                hotspot_id=f"hotspot_{city}_{idx}",
                cluster_id=idx,
                city=city or str(group["city"].iloc[0]),
                center_lat=round(float(group["lat"].mean()), 6),
                center_lon=round(float(group["lon"].mean()), 6),
                radius_km=0.8,
                num_segments=int(group["segment_id"].nunique()),
                avg_congestion=round(float((group["freeFlowSpeed"] - group["currentSpeed"]).clip(lower=0).mean()), 3),
                avg_jam_factor=round(avg_jam, 2),
                severity=sev,
                detected_at=group["timestamp"].max().to_pydatetime(),
            )
        )

    if severity:
        hotspots = [h for h in hotspots if h.severity == severity.lower()]

    return sorted(hotspots, key=lambda item: item.avg_jam_factor, reverse=True)


@router.get("/predicted", response_model=List[PredictedHotspot])
def get_predicted_hotspots(
    city: str = Query("hanoi", description="Filter by city"),
    horizon: str = Query("15m", description="Forecast horizon (15m or 60m)"),
):
    """Get demo predicted congestion hotspots from local gold data and the speed model."""
    city = normalize_city(city)
    try:
        horizon = normalize_horizon(horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        return []

    hotspots: list[PredictedHotspot] = []
    for row in latest.itertuples(index=False):
        segment_id = str(row.segment_id)
        try:
            prediction = predict_for_segment(segment_id, horizon)
        except (ModelUnavailableError, DataUnavailableError) as exc:
            logger.warning("Skipping predicted hotspot for %s: %s", segment_id, exc)
            continue
        except Exception as exc:  # pragma: no cover - defensive per-segment isolation
            logger.warning("Skipping predicted hotspot for %s after unexpected error: %s", segment_id, exc)
            continue

        if prediction.predicted_speed is None:
            continue

        current_speed = float(getattr(row, "currentSpeed", prediction.current_speed or 0.0))
        free_flow_speed = float(getattr(row, "freeFlowSpeed", 0.0))
        predicted_speed = float(prediction.predicted_speed)
        reasons: list[str] = []

        if predicted_speed < 20:
            reasons.append("predicted_speed_below_20_kph")
        if free_flow_speed > 0 and predicted_speed / free_flow_speed < 0.5:
            reasons.append("predicted_speed_below_half_free_flow")
        if current_speed > 0 and predicted_speed < current_speed * 0.7:
            reasons.append("predicted_speed_drop_over_30_percent")

        if not reasons:
            continue

        severity_score = len(reasons)
        risk_level = "critical" if severity_score >= 2 or predicted_speed < 15 else "high"
        geometry = getattr(row, "geometry", None)
        if geometry != geometry:  # NaN guard without importing pandas here.
            geometry = None

        hotspots.append(
            PredictedHotspot(
                segment_id=segment_id,
                road_name=str(getattr(row, "segment_name", segment_id) or segment_id),
                city=city or str(getattr(row, "city", "")),
                current_speed=round(current_speed, 3),
                predicted_speed=round(predicted_speed, 3),
                free_flow_speed=round(free_flow_speed, 3),
                horizon=horizon,
                risk_level=risk_level,
                reason=", ".join(reasons),
                latest_timestamp=prediction.latest_timestamp,
                geometry=geometry,
                model_name=prediction.model_name,
                filled_feature_count=prediction.filled_feature_count,
                is_fallback=prediction.is_fallback,
            )
        )

    return sorted(hotspots, key=lambda item: (item.risk_level != "critical", item.predicted_speed))
