"""Train lightweight local API forecast models from Gold parquet datasets."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "gold"
OUTPUT_DIR = PROJECT_ROOT / "results" / "cta_training_outputs_balanced_v3_latest"

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
    }


def main() -> None:
    summary = [train_horizon(15), train_horizon(60)]
    (OUTPUT_DIR / "training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame(summary).to_csv(OUTPUT_DIR / "metrics_all_models.csv", index=False)
    for item in summary:
        print(
            f"{item['task']}: wrote {item['artifact']} "
            f"rows={item['rows']} features={item['feature_count']} mae={item['mae']:.3f}"
        )


if __name__ == "__main__":
    main()
