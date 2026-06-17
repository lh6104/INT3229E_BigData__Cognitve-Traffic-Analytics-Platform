"""Optional MLflow helpers that never make Kaggle/local notebooks fail."""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _http_tracking_uri_reachable(uri: str, timeout_seconds: float = 2.0) -> tuple[bool, str | None]:
    parsed = urlparse(uri)
    if parsed.scheme not in {"http", "https"}:
        return True, None
    host = parsed.hostname
    if not host:
        return False, "tracking URI host is missing"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True, None
    except OSError as exc:
        return False, str(exc)


def log_training_run(
    *,
    experiment_name: str,
    run_name: str,
    dataset_path: str,
    dataset_row_count: int,
    feature_columns: list[str],
    model_type: str,
    hyperparameters: dict[str, Any],
    metrics: dict[str, Any],
    artifact_paths: list[Path],
) -> dict[str, Any]:
    """Log a training run when MLflow is configured; otherwise return skipped status."""
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        return {"status": "skipped", "reason": "MLFLOW_TRACKING_URI is not set"}
    reachable, reason = _http_tracking_uri_reachable(tracking_uri)
    if not reachable:
        return {
            "status": "skipped",
            "reason": f"MLflow tracking server is not reachable: {reason}",
            "tracking_uri": tracking_uri,
        }
    try:
        import mlflow
    except Exception as exc:
        return {"status": "skipped", "reason": f"mlflow import failed: {exc}"}
    try:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=run_name):
            mlflow.log_param("dataset_path", dataset_path)
            mlflow.log_param("dataset_row_count", dataset_row_count)
            mlflow.log_param("feature_count", len(feature_columns))
            mlflow.log_param("model_type", model_type)
            for key, value in hyperparameters.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    mlflow.log_param(key, value)
            for key, value in metrics.items():
                if isinstance(value, (int, float)) and value is not None:
                    mlflow.log_metric(key, float(value))
            for path in artifact_paths:
                if path.exists():
                    mlflow.log_artifact(str(path))
            run_id = mlflow.active_run().info.run_id
        return {"status": "logged", "tracking_uri": tracking_uri, "run_id": run_id}
    except Exception as exc:
        return {"status": "skipped", "reason": f"mlflow logging failed: {exc}", "tracking_uri": tracking_uri}
