"""System status endpoint backed by local runtime and generated reports."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter

from api.services.local_data import DATA_DIR, PROJECT_ROOT, DataUnavailableError, latest_by_segment, traffic_features, train_features
from api.services.model_inference import ModelUnavailableError, model_status, predict_for_segment

router = APIRouter()
START_TIME = time.monotonic()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _endpoint_p95(report: dict[str, Any] | None, path_fragment: str) -> float | None:
    if not report:
        return None
    for item in report.get("endpoints", []):
        if path_fragment in str(item.get("endpoint", "")):
            value = item.get("p95_ms")
            return float(value) if isinstance(value, (int, float)) else None
    return None


def _relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def _first_report(*paths: Path) -> tuple[Path | None, dict[str, Any] | None]:
    for path in paths:
        report = _read_json(path)
        if report is not None:
            return path, report
    return None, None


def _gold_data_status() -> dict[str, Any]:
    try:
        df = traffic_features().copy()
        latest = latest_by_segment(df)
    except DataUnavailableError as exc:
        return {
            "status": "not_available",
            "error": str(exc),
            "gold_row_count": 0,
            "segment_count": 0,
            "latest_data_timestamp": None,
            "data_freshness_minutes": None,
        }

    df["timestamp"] = pd.to_datetime(df.get("timestamp", df.get("time_bucket")), errors="coerce")
    max_ts = df["timestamp"].dropna().max() if "timestamp" in df else pd.NaT
    latest_iso = None
    freshness_minutes = None
    if pd.notna(max_ts):
        latest_dt = max_ts.to_pydatetime()
        if latest_dt.tzinfo is None:
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
        latest_iso = latest_dt.isoformat()
        freshness_minutes = round(max(0.0, (_utcnow() - latest_dt).total_seconds() / 60.0), 2)

    return {
        "status": "ok" if not latest.empty else "degraded",
        "gold_row_count": int(len(df)),
        "segment_count": int(latest["segment_id"].nunique()) if "segment_id" in latest else 0,
        "latest_data_timestamp": latest_iso,
        "data_freshness_minutes": freshness_minutes,
            "data_source": _relative_path(DATA_DIR / "gold"),
            "serving_snapshot_rows": int(len(latest)),
        }


def _model_status_summary() -> dict[str, Any]:
    status = model_status(load_models=True)
    horizons = status.get("horizons", {})
    first_loaded = next((item for item in horizons.values() if item.get("loaded")), None)
    coverage_values: list[float] = []
    try:
        latest = latest_by_segment(traffic_features(), "hanoi").head(20)
        for row in latest.itertuples(index=False):
            try:
                prediction = predict_for_segment(str(row.segment_id), "15m")
            except (ModelUnavailableError, DataUnavailableError):
                continue
            if prediction.required_feature_count:
                coverage_values.append(prediction.available_feature_count / prediction.required_feature_count)
    except DataUnavailableError:
        pass

    avg_coverage = round(sum(coverage_values) / len(coverage_values), 4) if coverage_values else None
    return {
        "loaded": bool(first_loaded),
        "ready": bool(status.get("ready")),
        "model_name": first_loaded.get("model_name") if first_loaded else None,
        "model_family": first_loaded.get("model_class") if first_loaded else None,
        "required_feature_count": first_loaded.get("feature_count") if first_loaded else None,
        "average_feature_coverage_ratio": avg_coverage,
        "feature_coverage_status": "measured_on_latest_hanoi_sample" if coverage_values else "not_measured",
        "horizons": horizons,
    }


def _performance_status() -> dict[str, Any]:
    report_path, report = _first_report(
        PROJECT_ROOT / "reports" / "api_benchmark.json",
        PROJECT_ROOT / "docs" / "performance_report.json",
    )
    extra = report.get("extra_metrics", {}) if report else {}
    model_runtime = extra.get("model_runtime", {}) if isinstance(extra, dict) else {}
    api_memory = extra.get("api_memory_after_model_load", {}) if isinstance(extra, dict) else {}
    frontend_build = extra.get("frontend_build", {}) if isinstance(extra, dict) else {}
    if not isinstance(model_runtime, dict):
        model_runtime = {}
    if not isinstance(api_memory, dict):
        api_memory = {}
    if not isinstance(frontend_build, dict):
        frontend_build = {}
    return {
        "last_benchmark_at": report.get("generated_at") if report else None,
        "forecast_p95_ms": _endpoint_p95(report, "/traffic/predict/HN_005?horizon=15m"),
        "dashboard_summary_p95_ms": _endpoint_p95(report, "/dashboard/summary"),
        "predicted_hotspots_p95_ms": _endpoint_p95(report, "/hotspots/predicted"),
        "system_status_p95_ms": _endpoint_p95(report, "/system/status"),
        "report": _relative_path(report_path) if report_path else None,
        "model_load_time_ms": model_runtime.get("model_load_time_ms"),
        "model_inference_time_ms": model_runtime.get("model_inference_time_ms"),
        "api_memory_after_model_load_mb": api_memory.get("total_rss_mb"),
        "frontend_build_status": frontend_build.get("status"),
        "frontend_build_detail": frontend_build.get("detail"),
        "status": "measured" if report else "not_measured",
    }


def _streaming_status() -> dict[str, Any]:
    report_path, report = _first_report(
        PROJECT_ROOT / "reports" / "streaming_demo_report.json",
        PROJECT_ROOT / "docs" / "streaming_demo_report.json",
    )
    if not report:
        return {
            "kafka_enabled": False,
            "status": "bounded_replay_not_run",
            "last_demo_at": None,
            "mode": "bounded_replay_demo",
        }
    return {
        "kafka_enabled": bool(report.get("kafka_enabled")),
        "status": report.get("overall_status", "not_available"),
        "last_demo_at": report.get("generated_at"),
        "mode": "bounded_replay_demo",
        "counts": {
            "produced": report.get("produced"),
            "consumed": report.get("consumed"),
            "bronze_written": report.get("bronze_written"),
            "dlq_written": report.get("dlq_written"),
            "validation_errors": report.get("validation_errors"),
        },
        "report": _relative_path(report_path) if report_path else None,
    }


def _configured(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    return bool(lowered) and not lowered.startswith("replace-with")


def _local_stack_status() -> dict[str, Any]:
    schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL")
    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    return {
        "status": "configured",
        "components": {
            "redis": {"status": "configured", "url": os.getenv("REDIS_URL", "redis://localhost:6380/0")},
            "kafka": {"status": "configured", "bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")},
            "schema_registry": {"status": "not_configured", "url": schema_registry_url},
            "minio": {"status": "configured" if minio_endpoint else "optional", "endpoint": minio_endpoint or "localhost:9000"},
            "postgres": {"status": "configured", "database": os.getenv("POSTGRES_DB", "traffic_analytics")},
        },
    }


def _cloud_status() -> dict[str, Any]:
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    s3_bucket = os.getenv("S3_BUCKET")
    s3_region = os.getenv("AWS_REGION", "ap-southeast-1")
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    s3_configured = _configured(aws_key) and _configured(aws_secret) and _configured(s3_bucket)
    neo4j_configured = _configured(neo4j_uri) and _configured(neo4j_user) and _configured(neo4j_password)
    return {
        "status": "future_configured" if s3_configured and neo4j_configured else "future_partial" if s3_configured or neo4j_configured else "future_not_configured",
        "scope": "future_optional_not_required_for_local_app",
        "s3": {
            "status": "future_configured" if s3_configured else "future_not_configured",
            "bucket": s3_bucket if _configured(s3_bucket) else None,
            "region": s3_region,
            "warehouse": os.getenv("S3_WAREHOUSE") if _configured(os.getenv("S3_WAREHOUSE")) else None,
            "verification": "configuration_only",
        },
        "neo4j_aura": {
            "status": "future_configured" if neo4j_configured else "future_not_configured",
            "uri": neo4j_uri if _configured(neo4j_uri) else None,
            "database": os.getenv("NEO4J_DATABASE") if _configured(os.getenv("NEO4J_DATABASE")) else None,
            "verification": "use scripts/check_neo4j_aura.py for live connectivity",
        },
    }


def _pipeline_manifest_summary() -> dict[str, Any]:
    path, report = _first_report(PROJECT_ROOT / "reports" / "pipeline_run_manifest.json")
    if not report:
        return {"status": "not_available", "report": None}
    stages = report.get("stages", [])
    failed = [stage.get("stage_name") for stage in stages if stage.get("status") == "failed"]
    return {
        "status": report.get("status", "unknown"),
        "run_id": report.get("run_id"),
        "start_time_utc": report.get("start_time_utc"),
        "end_time_utc": report.get("end_time_utc"),
        "duration_seconds": report.get("duration_seconds"),
        "stage_count": len(stages) if isinstance(stages, list) else None,
        "failed_stages": failed,
        "row_counts": report.get("summary", {}).get("row_counts", {}) if isinstance(report.get("summary"), dict) else {},
        "report": _relative_path(path) if path else None,
    }


def _dq_summary() -> dict[str, Any]:
    path, report = _first_report(PROJECT_ROOT / "reports" / "data_quality_report.json")
    if not report:
        return {"status": "not_available", "report": None}
    results = report.get("results", [])
    failures = [item for item in results if item.get("status") == "FAIL"]
    warnings = [item for item in results if item.get("status") == "WARN"]
    critical_failures = [item for item in failures if item.get("critical")]
    freshness = next((item for item in results if item.get("name") == "freshness"), None)
    status = "FAIL" if critical_failures else "WARN" if failures or warnings else "PASS"
    return {
        "status": status,
        "generated_at": report.get("metadata", {}).get("generated_at"),
        "dataset": report.get("metadata", {}).get("dataset"),
        "layer": report.get("metadata", {}).get("layer"),
        "rows": report.get("metadata", {}).get("rows"),
        "check_count": len(results) if isinstance(results, list) else None,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "critical_failure_count": len(critical_failures),
        "freshness": freshness,
        "report": _relative_path(path) if path else None,
    }


def _benchmark_summary() -> dict[str, Any]:
    path, report = _first_report(PROJECT_ROOT / "reports" / "api_benchmark.json")
    if not report:
        return {"status": "not_measured", "report": None}
    endpoints = report.get("endpoints", [])
    p95_values = [float(item["p95_ms"]) for item in endpoints if isinstance(item.get("p95_ms"), (int, float))]
    p50_values = [float(item["p50_ms"]) for item in endpoints if isinstance(item.get("p50_ms"), (int, float))]
    success_rates = [float(item["success_rate"]) for item in endpoints if isinstance(item.get("success_rate"), (int, float))]
    error_count = sum(int(item.get("error_count", 0) or 0) for item in endpoints)
    return {
        "status": "measured",
        "generated_at": report.get("generated_at"),
        "base_url": report.get("base_url"),
        "requests_per_endpoint": report.get("requests_per_endpoint"),
        "p50_ms": round(max(p50_values), 2) if p50_values else None,
        "p95_ms": round(max(p95_values), 2) if p95_values else None,
        "success_rate": round(min(success_rates), 4) if success_rates else None,
        "error_count": error_count,
        "endpoints": endpoints,
        "report": _relative_path(path) if path else None,
    }


def _model_evidence() -> dict[str, Any]:
    status = model_status(load_models=False)
    horizons = status.get("horizons", {})
    existing = {horizon: item for horizon, item in horizons.items() if item.get("exists")}
    first = next(iter(existing.values()), None)
    training_rows = 0
    for minutes in (15, 60, 240):
        try:
            training_rows += int(len(train_features(minutes)))
        except DataUnavailableError:
            continue
    return {
        "status": "available" if existing else "missing",
        "ready": bool(status.get("ready")),
        "artifact_dir": status.get("model_dir"),
        "artifact_version": first.get("artifact") if first else None,
        "available_horizons": list(existing.keys()),
        "training_rows": training_rows,
        "horizons": horizons,
    }


def _freshness_summary(data_status: dict[str, Any]) -> dict[str, Any]:
    minutes = data_status.get("data_freshness_minutes")
    if minutes is None:
        return {"status": "not_available", "age_hours": None, "last_updated": data_status.get("latest_data_timestamp")}
    age_hours = round(float(minutes) / 60.0, 2)
    status = "stale" if age_hours > 168 else "fresh"
    warning = None
    if status == "stale":
        warning = "Local static data is older than 168 hours; acceptable for demo evidence, not an operational SLA."
    return {
        "status": status,
        "age_hours": age_hours,
        "last_updated": data_status.get("latest_data_timestamp"),
        "warning": warning,
    }


def _overall_status(
    data: dict[str, Any],
    dq: dict[str, Any],
    model: dict[str, Any],
    benchmark: dict[str, Any],
    freshness: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if data.get("status") == "not_available":
        reasons.append("Gold data is not available.")
    if dq.get("status") == "FAIL":
        reasons.append("Data quality has critical failures.")
    elif dq.get("status") in {"WARN", "not_available"}:
        reasons.append("Data quality evidence is warning or unavailable.")
    if model.get("status") != "available":
        reasons.append("Model artifact is missing.")
    if benchmark.get("status") != "measured":
        reasons.append("API benchmark report is not available.")
    if freshness.get("status") == "stale":
        reasons.append("Local data is stale for an operational system.")
    if data.get("status") == "not_available" or dq.get("status") == "FAIL":
        return "Unhealthy", reasons
    if reasons:
        return "Degraded", reasons
    return "OK", reasons


@router.get("/status")
def get_system_status() -> dict[str, Any]:
    """Return demo-operability status without claiming production telemetry."""
    return {
        "api": {
            "status": "ok",
            "uptime_seconds": round(time.monotonic() - START_TIME, 2),
            "generated_at": _utcnow().isoformat(),
        },
        "data": _gold_data_status(),
        "model": _model_status_summary(),
        "performance": _performance_status(),
        "streaming": _streaming_status(),
        "local_stack": _local_stack_status(),
        "cloud": _cloud_status(),
    }


@router.get("/evidence")
def get_system_evidence() -> dict[str, Any]:
    """Return generated evidence for the local traffic application workflow."""
    data = _gold_data_status()
    pipeline = _pipeline_manifest_summary()
    dq = _dq_summary()
    benchmark = _benchmark_summary()
    model = _model_evidence()
    freshness = _freshness_summary(data)
    streaming = _streaming_status()
    overall_status, reasons = _overall_status(data, dq, model, benchmark, freshness)
    limitations = [
        "Local production-like demo; no production SLA is claimed.",
        "Gold/Parquet files are the serving source for the verified local path.",
        "Kafka is a bounded replay demo when its report exists, not continuous streaming.",
        "MLflow is experiment tracking only, not production registry serving.",
        "Graph and cloud/lakehouse services are optional or future unless explicitly verified.",
        "Implemented explanations use single-feature baseline perturbation, not SHAP.",
    ]
    return {
        "generated_at": _utcnow().isoformat(),
        "overall_status": overall_status,
        "reasons": reasons,
        "data": data,
        "data_freshness": freshness,
        "pipeline_run_manifest": pipeline,
        "dq_report": dq,
        "contract_validation": {
            "status": dq.get("status"),
            "contract": "docs/data_contracts/contracts.yaml",
        },
        "api_benchmark": benchmark,
        "model": model,
        "streaming_demo": streaming,
        "optional_services": {
            "neo4j": _cloud_status()["neo4j_aura"],
            "mlflow": {"status": "tracking_only_optional", "required_for_serving": False},
        },
        "limitations": limitations,
    }
