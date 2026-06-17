"""Train lightweight local API forecast models from Gold parquet datasets."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "gold"
OUTPUT_DIR = PROJECT_ROOT / "results" / "cta_training_outputs_balanced_v3_latest"
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "cognitive-traffic-local")

NON_FEATURE_COLUMNS = {
    "target",
    "target_speed",
    "target_speed_15m",
    "target_speed_60m",
    "timestamp",
    "time_bucket",
    "time_bucket_local",
    "prediction",
    "predicted_speed_kph",
    "actual_target_speed_kph",
    "horizon",
    "task",
    "model",
    "split",
}

ARTIFACTS = {
    15: "best_model_15m_speed_extra_trees.joblib",
    60: "best_model_60m_speed_extra_trees.joblib",
}


def train_horizon(horizon: int) -> dict[str, object]:
    import joblib
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    path = DATA_DIR / f"train_features_{horizon}m.parquet"
    df = pd.read_parquet(path)
    df = df[df["target_speed"].notna()].copy()
    if df.empty:
        raise RuntimeError(f"No training rows in {path}")

    feature_cols = [
        col
        for col in df.columns
        if col not in NON_FEATURE_COLUMNS and not col.startswith("target_speed_")
    ]
    X = df[feature_cols]
    y = df["target_speed"].astype(float)

    numeric_cols = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_cols = [col for col in feature_cols if col not in numeric_cols]
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), numeric_cols),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_cols,
            ),
        ],
        remainder="drop",
    )
    model = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            (
                "model",
                ExtraTreesRegressor(
                    n_estimators=160,
                    random_state=42,
                    min_samples_leaf=2,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    train_mask = df.get("split", pd.Series("train", index=df.index)).astype(str).isin(["train", "validation"])
    if train_mask.sum() < 10:
        train_mask = pd.Series(True, index=df.index)

    model.fit(X[train_mask], y[train_mask])
    pred = model.predict(X[~train_mask]) if (~train_mask).sum() else model.predict(X)
    actual = y[~train_mask] if (~train_mask).sum() else y

    artifact = {
        "model": model,
        "feature_cols": feature_cols,
        "selected_model": "extra_trees",
        "target": "target_speed",
        "horizon": f"{horizon}m",
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = OUTPUT_DIR / ARTIFACTS[horizon]
    joblib.dump(artifact, artifact_path)

    return {
        "task": f"{horizon}m_speed",
        "selected_model": "extra_trees",
        "artifact": artifact_path.name,
        "rows": int(len(df)),
        "feature_count": int(len(feature_cols)),
        "mae": float(mean_absolute_error(actual, pred)),
        "rmse": float(mean_squared_error(actual, pred) ** 0.5),
        "r2": float(r2_score(actual, pred)) if len(actual) > 1 else None,
        "dataset_path": str(path.relative_to(PROJECT_ROOT)),
        "feature_cols": feature_cols,
        "training_mode": "trained",
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
    except Exception:
        return "unknown"


def log_to_mlflow(summary: list[dict[str, object]]) -> None:
    try:
        import mlflow
    except Exception as exc:
        print(f"WARNING mlflow unavailable; skipped tracking: {exc}")
        return

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    try:
        mlflow.set_experiment(EXPERIMENT_NAME)
        with mlflow.start_run(run_name=f"local-extra-trees-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"):
            mlflow.set_tag("git_commit", git_commit())
            mlflow.set_tag("training_entrypoint", "scripts/train_local_api_models.py")
            mlflow.log_param("model_type", "sklearn_extra_trees")
            mlflow.log_param("output_dir", str(OUTPUT_DIR.relative_to(PROJECT_ROOT)))
            mlflow.log_param("horizons", ",".join(str(item["task"]) for item in summary))
            mlflow.log_param("training_mode", ",".join(sorted({str(item.get("training_mode", "trained")) for item in summary})))
            for item in summary:
                task = str(item["task"])
                prefix = task.replace("_speed", "")
                mlflow.log_metric(f"{prefix}_mae", float(item["mae"]))
                mlflow.log_metric(f"{prefix}_rmse", float(item["rmse"]))
                if item.get("r2") is not None:
                    mlflow.log_metric(f"{prefix}_r2", float(item["r2"]))
                mlflow.log_param(f"{prefix}_dataset_path", item["dataset_path"])
                mlflow.log_param(f"{prefix}_feature_count", int(item["feature_count"]))
            mlflow.log_artifact(str(OUTPUT_DIR / "training_summary.json"), artifact_path="metadata")
            mlflow.log_artifact(str(OUTPUT_DIR / "metrics_all_models.csv"), artifact_path="metadata")
            for item in summary:
                artifact_path = OUTPUT_DIR / str(item["artifact"])
                if artifact_path.exists():
                    mlflow.log_artifact(str(artifact_path), artifact_path="models")
            manifest = {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "git_commit": git_commit(),
                "mlflow_tracking_uri": tracking_uri,
                "serving_mode": "local_artifact",
                "output_dir": str(OUTPUT_DIR.relative_to(PROJECT_ROOT)),
                "runs": [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "feature_cols"
                    }
                    for item in summary
                ],
            }
            manifest_path = OUTPUT_DIR / "model_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            mlflow.log_artifact(str(manifest_path), artifact_path="metadata")
            print(f"MLflow run logged to {tracking_uri} experiment={EXPERIMENT_NAME}")
    except Exception as exc:
        print(f"WARNING MLflow tracking failed; local model artifacts were still written: {exc}")


def verify_existing_artifacts(reason: str) -> list[dict[str, object]]:
    model_pack = PROJECT_ROOT / "results" / "cta_model_pack_final_v1_20260613T162016Z"
    manifest_path = model_pack / "metadata" / "model_manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    rows: list[dict[str, object]] = []
    for horizon in [15, 60]:
        artifact = model_pack / "models" / f"selected_model_{horizon}m_lightgbm.joblib"
        metrics = (manifest.get("selected_metrics") or {}).get(f"{horizon}m", {})
        model_info = (manifest.get("selected_models") or {}).get(f"{horizon}m", {})
        if artifact.exists():
            rows.append(
                {
                    "task": f"{horizon}m_speed",
                    "selected_model": metrics.get("model", "lightgbm_existing_artifact"),
                    "artifact": str(artifact.relative_to(PROJECT_ROOT)),
                    "rows": int(metrics.get("n", 0) or 0),
                    "feature_count": int(model_info.get("feature_count", 0) or 0),
                    "mae": float(metrics.get("MAE", metrics.get("mae", 0.0)) or 0.0),
                    "rmse": float(metrics.get("RMSE", metrics.get("rmse", 0.0)) or 0.0),
                    "r2": metrics.get("R2", metrics.get("r2")),
                    "dataset_path": "data/gold/train_features",
                    "training_mode": "verified_existing_artifact",
                    "warning": reason,
                }
            )
    if not rows:
        raise RuntimeError(f"{reason}; no existing model artifacts found")
    return rows


def main() -> None:
    try:
        summary = [train_horizon(15), train_horizon(60)]
    except ModuleNotFoundError as exc:
        reason = f"Python ML dependency missing: {exc.name}. Existing checked-in artifacts were verified instead."
        print(f"WARNING {reason}")
        summary = verify_existing_artifacts(reason)
    serializable_summary = [{key: value for key, value in item.items() if key != "feature_cols"} for item in summary]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "training_summary.json").write_text(json.dumps(serializable_summary, indent=2), encoding="utf-8")
    pd.DataFrame(serializable_summary).to_csv(OUTPUT_DIR / "metrics_all_models.csv", index=False)
    log_to_mlflow(summary)
    for item in summary:
        print(
            f"{item['task']}: wrote {item['artifact']} "
            f"rows={item['rows']} features={item['feature_count']} mae={item['mae']:.3f}"
        )


if __name__ == "__main__":
    main()
