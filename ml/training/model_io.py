"""Model artifact and manifest IO helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


DEFAULT_LIMITATIONS = [
    "Model validity depends on the quality and realism of the training dataset.",
    "If trained on synthetic/calibrated data, real-world predictive performance is not guaranteed.",
]


def save_model_artifact(model: Any, output_dir: Path, filename: str = "traffic_model.joblib") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    joblib.dump(model, path)
    return path


def save_metrics(metrics: dict[str, Any], output_dir: Path, filename: str = "metrics.json") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    return path


def save_feature_importance(feature_importance: pd.DataFrame, output_dir: Path, filename: str = "feature_importance.csv") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    feature_importance.to_csv(path, index=False)
    return path


def build_model_manifest(
    *,
    model_name: str,
    model_type: str,
    dataset_path: str,
    target_column: str,
    feature_columns: list[str],
    metrics: dict[str, Any],
    artifact_path: str,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "model_type": model_type,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": dataset_path,
        "target_column": target_column,
        "feature_columns": feature_columns,
        "metrics": {
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "mape": metrics.get("mape"),
            "r2": metrics.get("r2"),
        },
        "artifact_path": artifact_path,
        "limitations": limitations or DEFAULT_LIMITATIONS,
    }


def save_model_manifest(manifest: dict[str, Any], output_dir: Path, filename: str = "model_manifest.json") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path
