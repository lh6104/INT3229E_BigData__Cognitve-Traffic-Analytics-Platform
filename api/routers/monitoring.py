"""Pipeline and model monitoring endpoints backed by local project state."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timezone
import logging
from pathlib import Path

import pandas as pd

from api.services.local_data import DATA_DIR, PROJECT_ROOT, DataUnavailableError, traffic_features
from api.services.model_inference import model_status

logger = logging.getLogger(__name__)

router = APIRouter()


class PipelineStatus(BaseModel):
    """Data pipeline health status."""
    component: str
    status: str  # healthy, degraded, unhealthy
    lag_messages: int
    last_update: datetime
    details: dict


class ModelMetrics(BaseModel):
    """Model performance metrics."""
    horizon_minutes: int
    mae: float
    rmse: float
    r2_score: float
    rows: int
    feature_count: int
    artifact: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _status_from_age(hours: float | None) -> str:
    if hours is None:
        return "unhealthy"
    hours = max(0.0, hours)
    if hours <= 24:
        return "healthy"
    if hours <= 168:
        return "degraded"
    return "unhealthy"


def _status_from_ratio(ratio: float | None, warn: float, error: float, lower_is_better: bool = True) -> str:
    if ratio is None:
        return "unhealthy"
    if lower_is_better:
        if ratio >= error:
            return "unhealthy"
        if ratio >= warn:
            return "degraded"
        return "healthy"
    if ratio <= error:
        return "unhealthy"
    if ratio <= warn:
        return "degraded"
    return "healthy"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        logger.exception("Could not read monitoring CSV %s", path)
        return pd.DataFrame()


def _data_quality_summary() -> dict[str, Any]:
    report = _read_csv(DATA_DIR / "gold" / "data_quality_report.csv")
    if report.empty:
        return {
            "segments": 0,
            "record_count": 0,
            "missing_bucket_ratio": None,
            "correct_interval_ratio": None,
            "train_candidate_15m": 0,
            "train_candidate_60m": 0,
        }
    return {
        "segments": int(report["segment_id"].nunique()) if "segment_id" in report else int(len(report)),
        "record_count": int(report.get("record_count", pd.Series(dtype=float)).sum()),
        "missing_bucket_ratio": round(float(report.get("missing_bucket_ratio", pd.Series([0])).mean()), 4),
        "correct_interval_ratio": round(float(report.get("correct_5m_interval_ratio", pd.Series([0])).mean()), 4),
        "train_candidate_15m": int(report.get("is_train_candidate_15m", pd.Series(dtype=bool)).sum()),
        "train_candidate_60m": int(report.get("is_train_candidate_60m", pd.Series(dtype=bool)).sum()),
    }


def _dataset_component(name: str, path: Path) -> PipelineStatus:
    if not path.exists():
        return PipelineStatus(
            component=name,
            status="unhealthy",
            lag_messages=1,
            last_update=_utcnow(),
            details={"path": str(path.relative_to(PROJECT_ROOT)), "exists": False},
        )
    modified_at = _file_mtime(path)
    age_hours = max(0.0, (_utcnow() - modified_at).total_seconds() / 3600)
    return PipelineStatus(
        component=name,
        status=_status_from_age(age_hours),
        lag_messages=0 if age_hours <= 24 else int(age_hours),
        last_update=modified_at,
        details={
            "path": str(path.relative_to(PROJECT_ROOT)),
            "exists": True,
            "size_bytes": path.stat().st_size,
            "age_hours": round(age_hours, 2),
        },
    )


@router.get("/pipeline", response_model=List[PipelineStatus])
def get_pipeline_status():
    """Get local pipeline health status.

    Returns:
        List of component statuses derived from local data/model artifacts
    """
    now = _utcnow()
    components: list[PipelineStatus] = []

    try:
        traffic = traffic_features().copy()
        traffic["timestamp"] = pd.to_datetime(traffic.get("timestamp", traffic.get("time_bucket")), errors="coerce")
        traffic = traffic.dropna(subset=["timestamp"])
        latest_ts = traffic["timestamp"].max()
        latest_dt = latest_ts.to_pydatetime()
        if latest_dt.tzinfo is None:
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (now - latest_dt).total_seconds() / 3600)
        components.append(
            PipelineStatus(
                component="gold_traffic_features",
                status=_status_from_age(age_hours),
                lag_messages=0 if age_hours <= 24 else int(age_hours),
                last_update=latest_dt,
                details={
                    "rows": int(len(traffic)),
                    "segments": int(traffic["segment_id"].nunique()),
                    "cities": sorted(traffic["city"].dropna().astype(str).unique().tolist()) if "city" in traffic else [],
                    "latest_timestamp": latest_dt.isoformat(),
                    "age_hours": round(age_hours, 2),
                },
            )
        )
    except DataUnavailableError as exc:
        components.append(
            PipelineStatus(
                component="gold_traffic_features",
                status="unhealthy",
                lag_messages=1,
                last_update=now,
                details={"error": str(exc)},
            )
        )

    components.extend(
        [
            _dataset_component("silver_traffic_cleaned", DATA_DIR / "silver" / "traffic_cleaned.parquet"),
            _dataset_component("silver_weather_cleaned", DATA_DIR / "silver" / "weather_cleaned.parquet"),
            _dataset_component("silver_news_events", DATA_DIR / "silver" / "news_events_normalized.parquet"),
        ]
    )

    quality = _data_quality_summary()
    interval_ratio = quality.get("correct_interval_ratio")
    components.append(
        PipelineStatus(
            component="data_quality",
            status=_status_from_ratio(interval_ratio, warn=0.75, error=0.5, lower_is_better=False),
            lag_messages=0,
            last_update=_file_mtime(DATA_DIR / "gold" / "data_quality_report.csv")
            if (DATA_DIR / "gold" / "data_quality_report.csv").exists()
            else now,
            details=quality,
        )
    )

    models = model_status(load_models=True)
    components.append(
        PipelineStatus(
            component="forecast_models",
            status="healthy" if models.get("ready") else "unhealthy",
            lag_messages=0 if models.get("ready") else 1,
            last_update=now,
            details={
                "ready": models.get("ready"),
                "model_dir": models.get("model_dir"),
                "horizons": models.get("horizons", {}),
            },
        )
    )

    components.append(
        PipelineStatus(
            component="fastapi",
            status="healthy",
            lag_messages=0,
            last_update=now,
            details={"service": "traffic-api", "source": "local process"},
        )
    )
    return components


@router.get("/model", response_model=Dict)
def get_model_metrics():
    """Get model performance and data quality metrics.

    Returns:
        Model metrics (MAE, RMSE, R²) and data quality information
    """
    status = model_status(load_models=True)
    summary = status.get("training_summary") or []
    models = []
    for item in summary:
        task = str(item.get("task", ""))
        horizon = 15 if "15m" in task else 60 if "60m" in task else 0
        models.append(
            {
                "horizon_minutes": horizon,
                "mae": float(item.get("mae", 0.0)),
                "rmse": float(item.get("rmse", 0.0)),
                "r2_score": float(item.get("r2", 0.0)),
                "rows": int(item.get("rows", 0)),
                "feature_count": int(item.get("feature_count", 0)),
                "artifact": str(item.get("artifact", "")),
            }
        )

    quality = _data_quality_summary()
    missing_ratio = quality.get("missing_bucket_ratio")
    interval_ratio = quality.get("correct_interval_ratio")
    return {
        "ready": bool(status.get("ready")),
        "model_dir": status.get("model_dir"),
        "models": models,
        "data_quality": {
            **quality,
            "freshness_status": _status_from_ratio(missing_ratio, warn=0.5, error=0.8),
            "interval_status": _status_from_ratio(interval_ratio, warn=0.75, error=0.5, lower_is_better=False),
        },
        "horizons": status.get("horizons", {}),
    }
