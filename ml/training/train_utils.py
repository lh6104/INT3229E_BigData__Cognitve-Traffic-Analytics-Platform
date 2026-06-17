"""Reusable traffic forecasting training functions for notebooks and CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.training.features import FeatureSelection, infer_target_column, select_feature_columns, time_ordered_split
from ml.training.metrics import evaluate_regression


@dataclass
class TrainingResult:
    model: Any
    baseline_model: Any
    metrics: dict[str, Any]
    baseline_metrics: dict[str, Any]
    feature_selection: FeatureSelection
    train_rows: int
    validation_rows: int
    feature_importance: pd.DataFrame
    predictions: pd.DataFrame
    hyperparameters: dict[str, Any]


def load_training_dataset(path: Path) -> pd.DataFrame:
    """Load a CSV or Parquet training dataset."""
    if path.is_dir():
        parquet = path / "train_features_15m.parquet"
        csv = path / "train_features_15m.csv"
        path = parquet if parquet.exists() else csv
    if not path.exists():
        raise FileNotFoundError(f"Training dataset not found: {path}")
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def build_preprocessor(selection: FeatureSelection) -> ColumnTransformer:
    numeric = ("num", SimpleImputer(strategy="median"), selection.numeric_columns)
    categorical = (
        "cat",
        Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]
        ),
        selection.categorical_columns,
    )
    return ColumnTransformer(transformers=[numeric, categorical], remainder="drop")


def train_baseline_model(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    selection: FeatureSelection,
) -> tuple[Any, dict[str, Any]]:
    baseline = DummyRegressor(strategy="median")
    baseline.fit(train_df[selection.feature_columns], train_df[selection.target_column])
    pred = baseline.predict(validation_df[selection.feature_columns])
    return baseline, evaluate_regression(validation_df[selection.target_column], pred)


def _lightgbm_regressor(random_state: int, params: dict[str, Any] | None = None):
    try:
        from lightgbm import LGBMRegressor
    except Exception as exc:
        raise RuntimeError("LightGBM is required for this training workflow. Install `lightgbm` first.") from exc
    default_params: dict[str, Any] = {
        "objective": "regression",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": random_state,
        "n_jobs": -1,
        "verbose": -1,
    }
    if params:
        default_params.update(params)
    return LGBMRegressor(**default_params), default_params


def train_lightgbm_model(
    df: pd.DataFrame,
    target_column: str | None = None,
    validation_fraction: float = 0.2,
    random_state: int = 42,
    hyperparameters: dict[str, Any] | None = None,
) -> TrainingResult:
    """Train a baseline and LightGBM traffic forecasting model."""
    target = infer_target_column(df, target_column)
    work = df.dropna(subset=[target]).copy()
    selection = select_feature_columns(work, target)
    train_df, validation_df = time_ordered_split(work, validation_fraction=validation_fraction)
    if train_df.empty or validation_df.empty:
        raise ValueError("Training and validation splits must both be non-empty.")

    baseline_model, baseline_metrics = train_baseline_model(train_df, validation_df, selection)
    estimator, params = _lightgbm_regressor(random_state=random_state, params=hyperparameters)
    model = Pipeline(steps=[("preprocess", build_preprocessor(selection)), ("model", estimator)])
    model.fit(train_df[selection.feature_columns], train_df[target])

    predictions = model.predict(validation_df[selection.feature_columns])
    metrics = evaluate_regression(validation_df[target], predictions)
    prediction_frame = validation_df[[column for column in ["city", "segment_id", "time_bucket", "timestamp"] if column in validation_df.columns]].copy()
    prediction_frame["actual"] = validation_df[target].to_numpy()
    prediction_frame["prediction"] = predictions
    prediction_frame["absolute_error"] = (prediction_frame["actual"] - prediction_frame["prediction"]).abs()

    feature_importance = feature_importance_frame(model, selection)
    return TrainingResult(
        model=model,
        baseline_model=baseline_model,
        metrics=metrics,
        baseline_metrics=baseline_metrics,
        feature_selection=selection,
        train_rows=int(len(train_df)),
        validation_rows=int(len(validation_df)),
        feature_importance=feature_importance,
        predictions=prediction_frame,
        hyperparameters=params,
    )


def feature_importance_frame(model: Any, selection: FeatureSelection) -> pd.DataFrame:
    estimator = model.named_steps["model"] if isinstance(model, Pipeline) else model
    values = getattr(estimator, "feature_importances_", None)
    transformed_names = selection.feature_columns
    try:
        transformed_names = model.named_steps["preprocess"].get_feature_names_out().tolist()
    except Exception:
        pass
    if values is None:
        return pd.DataFrame({"feature": transformed_names, "importance": [0.0] * len(transformed_names)})
    return (
        pd.DataFrame({"feature": transformed_names[: len(values)], "importance": values})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
