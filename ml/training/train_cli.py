"""Headless training CLI used by Makefile, Airflow, and CI."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ml.tracking.mlflow_utils import log_training_run
from ml.training.model_io import build_model_manifest, save_feature_importance, save_metrics, save_model_artifact, save_model_manifest
from ml.training.train_utils import load_training_dataset, train_lightgbm_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/gold/train_features_15m.parquet")
    parser.add_argument("--output-dir", default="models/artifacts")
    parser.add_argument("--metadata-dir", default="models/metadata")
    parser.add_argument("--target-column", default=None)
    parser.add_argument("--experiment-name", default="cognitive-traffic-local-artifacts")
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    dataset_path = Path(args.input)
    output_dir = Path(args.output_dir)
    metadata_dir = Path(args.metadata_dir)
    df = load_training_dataset(dataset_path)
    result = train_lightgbm_model(df, target_column=args.target_column)

    model_path = save_model_artifact(result.model, output_dir, "traffic_model.joblib")
    metrics_path = save_metrics(result.metrics, metadata_dir, "metrics.json")
    importance_path = save_feature_importance(result.feature_importance, metadata_dir, "feature_importance.csv")
    manifest = build_model_manifest(
        model_name="traffic_forecasting_lightgbm",
        model_type="LightGBMRegressor",
        dataset_path=str(dataset_path),
        target_column=result.feature_selection.target_column,
        feature_columns=result.feature_selection.feature_columns,
        metrics=result.metrics,
        artifact_path=str(model_path),
    )
    manifest_path = save_model_manifest(manifest, metadata_dir, "model_manifest.json")
    mlflow_status = log_training_run(
        experiment_name=args.experiment_name,
        run_name=args.run_name or f"traffic-lightgbm-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        dataset_path=str(dataset_path),
        dataset_row_count=len(df),
        feature_columns=result.feature_selection.feature_columns,
        model_type="LightGBMRegressor",
        hyperparameters=result.hyperparameters,
        metrics=result.metrics,
        artifact_paths=[model_path, metrics_path, importance_path, manifest_path],
    )
    print(
        "PASS train_cli "
        f"rows={len(df)} train_rows={result.train_rows} validation_rows={result.validation_rows} "
        f"features={len(result.feature_selection.feature_columns)} "
        f"mae={result.metrics['mae']:.3f} rmse={result.metrics['rmse']:.3f} "
        f"model={model_path} manifest={manifest_path} mlflow={mlflow_status['status']}"
    )
    if mlflow_status.get("reason"):
        print(f"MLflow note: {mlflow_status['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
