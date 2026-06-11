"""Dashboard aggregate endpoints backed by local traffic data."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, traffic_features

router = APIRouter()


class DashboardSummary(BaseModel):
    city: str
    monitored_segments: int
    active_alerts: int
    free_flow_segments: int
    slow_segments: int
    congested_segments: int
    avg_speed: Optional[float]
    avg_jam_factor: Optional[float]
    latest_timestamp: Optional[datetime]
    data_source: str = "gold_local"
    is_demo: bool = False
    message: Optional[str] = None


class DashboardTrendPoint(BaseModel):
    timestamp: datetime
    avg_speed: float
    avg_jam_factor: float


class DashboardTrends(BaseModel):
    city: str
    hours: int
    points: List[DashboardTrendPoint]
    data_source: str = "gold_local"
    available_points: int
    min_timestamp: Optional[datetime]
    max_timestamp: Optional[datetime]
    is_demo: bool = False
    message: Optional[str] = None


def _empty_summary(city: str, message: str | None = None) -> DashboardSummary:
    return DashboardSummary(
        city=city,
        monitored_segments=0,
        active_alerts=0,
        free_flow_segments=0,
        slow_segments=0,
        congested_segments=0,
        avg_speed=None,
        avg_jam_factor=None,
        latest_timestamp=None,
        message=message,
    )


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(city: str = Query("hanoi", description="City code")):
    """Get latest city-level dashboard metrics from local gold traffic data."""
    city = normalize_city(city) or "hanoi"
    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        return _empty_summary(city, str(exc))

    if latest.empty:
        return _empty_summary(city, f"No local traffic data found for city '{city}'")

    return DashboardSummary(
        city=city,
        monitored_segments=int(latest["segment_id"].nunique()),
        active_alerts=int((latest["jamFactor"] >= 3).sum()),
        free_flow_segments=int((latest["jamFactor"] < 3).sum()),
        slow_segments=int(((latest["jamFactor"] >= 3) & (latest["jamFactor"] < 6)).sum()),
        congested_segments=int((latest["jamFactor"] >= 6).sum()),
        avg_speed=round(float(latest["currentSpeed"].mean()), 2),
        avg_jam_factor=round(float(latest["jamFactor"].mean()), 2),
        latest_timestamp=latest["timestamp"].max().to_pydatetime(),
    )


@router.get("/trends", response_model=DashboardTrends)
def get_dashboard_trends(
    city: str = Query("hanoi", description="City code"),
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
):
    """Get hourly average speed and jam factor trends from local gold traffic data."""
    city = normalize_city(city) or "hanoi"
    try:
        df = traffic_features().copy()
    except DataUnavailableError as exc:
        return DashboardTrends(
            city=city,
            hours=hours,
            points=[],
            available_points=0,
            min_timestamp=None,
            max_timestamp=None,
            message=str(exc),
        )

    if "city" in df.columns:
        df["city"] = df["city"].map(normalize_city)
        df = df[df["city"] == city]

    if df.empty:
        return DashboardTrends(
            city=city,
            hours=hours,
            points=[],
            available_points=0,
            min_timestamp=None,
            max_timestamp=None,
            message=f"No local traffic data found for city '{city}'",
        )

    df["timestamp"] = pd.to_datetime(df.get("timestamp", df.get("time_bucket")), errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return DashboardTrends(
            city=city,
            hours=hours,
            points=[],
            available_points=0,
            min_timestamp=None,
            max_timestamp=None,
            message=f"No valid timestamps found for city '{city}'",
        )

    max_timestamp = df["timestamp"].max()
    min_window = max_timestamp - pd.Timedelta(hours=hours)
    window = df[df["timestamp"] >= min_window].copy()
    grouped = (
        window.set_index("timestamp")
        .groupby(pd.Grouper(freq="h"))
        .agg(avg_speed=("currentSpeed", "mean"), avg_jam_factor=("jamFactor", "mean"))
        .dropna()
        .reset_index()
        .sort_values("timestamp")
    )

    points = [
        DashboardTrendPoint(
            timestamp=row.timestamp.to_pydatetime(),
            avg_speed=round(float(row.avg_speed), 2),
            avg_jam_factor=round(float(row.avg_jam_factor), 2),
        )
        for row in grouped.itertuples(index=False)
    ]

    return DashboardTrends(
        city=city,
        hours=hours,
        points=points,
        available_points=len(points),
        min_timestamp=window["timestamp"].min().to_pydatetime() if not window.empty else None,
        max_timestamp=max_timestamp.to_pydatetime(),
    )
