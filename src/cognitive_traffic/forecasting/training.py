"""Multi-horizon quantile training with explicit baseline comparisons."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
import pandas as pd
import pyarrow as pa
from lightgbm import LGBMRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cognitive_traffic.forecasting.baselines import HistoricalMedian, Persistence, SeasonalMedian
from cognitive_traffic.forecasting.evaluation import WalkForwardSplitter, pinball_loss, regression_metrics
from cognitive_traffic.forecasting.features import FEATURE_REGISTRY
from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.object_store import S3ObjectStore, read_parquet

QUANTILES = (0.1, 0.5, 0.9)


@dataclass
class QuantileModelBundle:
    models: dict[int, dict[float, Any]]
    feature_columns: tuple[str, ...]
    feature_version: str
    schema_version: str
    metrics: list[dict[str, Any]]

    def predict(self, frame: pd.DataFrame, horizon_minutes: int) -> pd.DataFrame:
        if horizon_minutes not in self.models:
            raise ValueError(f"unsupported horizon: {horizon_minutes}")
        matrix = frame.loc[:, self.feature_columns]
        values = {
            quantile: np.asarray(model.predict(matrix), dtype=float)
            for quantile, model in self.models[horizon_minutes].items()
        }
        # Independently trained quantiles can cross. Sorting preserves a valid
        # interval without pretending the correction improves calibration.
        ordered = np.sort(np.column_stack([values[q] for q in QUANTILES]), axis=1)
        return pd.DataFrame(ordered, columns=["p10", "p50", "p90"], index=frame.index).clip(lower=0)


def _feature_columns(frame: pd.DataFrame) -> tuple[str, ...]:
    columns = tuple(name for name in FEATURE_REGISTRY if name in frame and pd.api.types.is_numeric_dtype(frame[name]))
    if not columns:
        raise ValueError("training dataset contains no registered numeric features")
    return columns


def _model(alpha: float, random_state: int) -> LGBMRegressor:
    return LGBMRegressor(
        objective="quantile",
        alpha=alpha,
        n_estimators=400,
        learning_rate=0.04,
        num_leaves=31,
        min_child_samples=40,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=random_state,
        verbosity=-1,
    )


def train_quantile_bundle(
    frame: pd.DataFrame,
    *,
    targets: dict[int, str] | None = None,
    feature_version: str = "1",
    schema_version: str = "1",
    splitter: WalkForwardSplitter | None = None,
    random_state: int = 42,
) -> QuantileModelBundle:
    targets = targets or {15: "target_speed_15m", 60: "target_speed_60m", 240: "target_speed_240m"}
    missing = [column for column in targets.values() if column not in frame]
    if missing:
        raise ValueError(f"missing target columns: {missing}")
    columns = _feature_columns(frame)
    splitter = splitter or WalkForwardSplitter()
    folds = splitter.split(frame)
    metrics: list[dict[str, Any]] = []

    for horizon, target in targets.items():
        for fold in folds:
            train = frame.loc[fold.train_index].dropna(subset=[target, *columns])
            validation = frame.loc[fold.validation_index].dropna(subset=[target, *columns])
            if train.empty or validation.empty:
                continue
            baselines = (Persistence(), HistoricalMedian(), SeasonalMedian())
            for baseline in baselines:
                baseline.fit(train, target)
                predicted = baseline.predict(validation)
                metrics.append(
                    {
                        "model": baseline.name,
                        "horizon_minutes": horizon,
                        "fold": fold.number,
                        **regression_metrics(validation[target], predicted),
                    }
                )
            ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            ridge.fit(train.loc[:, columns], train[target])
            ridge_prediction = ridge.predict(validation.loc[:, columns])
            metrics.append(
                {
                    "model": "ridge",
                    "horizon_minutes": horizon,
                    "fold": fold.number,
                    **regression_metrics(validation[target], ridge_prediction),
                }
            )
            median_model = _model(0.5, random_state)
            median_model.fit(train.loc[:, columns], train[target])
            median_prediction = median_model.predict(validation.loc[:, columns])
            metrics.append(
                {
                    "model": "lightgbm_p50",
                    "horizon_minutes": horizon,
                    "fold": fold.number,
                    **regression_metrics(validation[target], median_prediction),
                }
            )

    models: dict[int, dict[float, Any]] = {}
    for horizon, target in targets.items():
        work = frame.dropna(subset=[target, *columns])
        models[horizon] = {}
        for quantile in QUANTILES:
            model = _model(quantile, random_state)
            model.fit(work.loc[:, columns], work[target])
            prediction = model.predict(work.loc[:, columns])
            metrics.append(
                {
                    "model": f"lightgbm_p{int(quantile * 100)}_final",
                    "horizon_minutes": horizon,
                    "fold": "full_training_window",
                    "pinball_loss": pinball_loss(work[target], prediction, quantile),
                }
            )
            models[horizon][quantile] = model
    return QuantileModelBundle(models, columns, feature_version, schema_version, metrics)


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    reasons: tuple[str, ...]


class PromotionGate:
    def __init__(self, *, maximum_champion_regression: float = 0.02, maximum_peak_mae: float = 12.0) -> None:
        self.maximum_champion_regression = maximum_champion_regression
        self.maximum_peak_mae = maximum_peak_mae

    def evaluate(
        self,
        *,
        candidate_mae: float,
        baseline_mae: float,
        champion_mae: float | None,
        peak_mae: float,
        leakage_passed: bool,
        data_quality_passed: bool,
        schema_compatible: bool,
    ) -> PromotionDecision:
        reasons: list[str] = []
        if candidate_mae >= baseline_mae:
            reasons.append("candidate does not beat the persistence baseline")
        if champion_mae is not None and candidate_mae > champion_mae * (1 + self.maximum_champion_regression):
            reasons.append("candidate regresses beyond the champion tolerance")
        if peak_mae > self.maximum_peak_mae:
            reasons.append("peak-hour MAE exceeds the configured limit")
        if not leakage_passed:
            reasons.append("point-in-time leakage checks failed")
        if not data_quality_passed:
            reasons.append("data-quality gate failed")
        if not schema_compatible:
            reasons.append("model signature is incompatible with serving")
        return PromotionDecision(not reasons, tuple(reasons))


def git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def log_mlflow_run(
    *,
    bundle: QuantileModelBundle,
    dataset_id: str,
    dataset_uri: str,
    source_start: str,
    source_end: str,
    parameters: dict[str, Any],
) -> tuple[str, str]:
    import mlflow
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "traffic-forecasting"))
    with mlflow.start_run() as run:
        mlflow.set_tags(
            {
                "git_sha": git_sha(),
                "dataset_id": dataset_id,
                "dataset_uri": dataset_uri,
                "source_start": source_start,
                "source_end": source_end,
                "schema_version": bundle.schema_version,
                "feature_version": bundle.feature_version,
            }
        )
        mlflow.log_params(parameters)
        for row in bundle.metrics:
            if row.get("fold") == "full_training_window" and "pinball_loss" in row:
                mlflow.log_metric(
                    f"h{row['horizon_minutes']}_{row['model']}_pinball", row["pinball_loss"]
                )
        with tempfile.TemporaryDirectory(prefix="traffic-model-") as directory:
            artifact = os.path.join(directory, "bundle.joblib")
            joblib.dump(bundle, artifact, compress=3)
            mlflow.log_artifact(artifact, artifact_path="model")
        run_id = run.info.run_id

    client = MlflowClient()
    try:
        client.create_registered_model(settings.model_name)
    except MlflowException as exc:
        if "already exists" not in str(exc).lower():
            raise
    version = client.create_model_version(
        name=settings.model_name,
        source=f"runs:/{run_id}/model",
        run_id=run_id,
        tags={"dataset_id": dataset_id, "feature_version": bundle.feature_version},
    )
    client.set_registered_model_alias(settings.model_name, "challenger", version.version)
    return run_id, str(version.version)


def promote_model_version(version: str) -> None:
    """Move the champion alias; using an older version performs a rollback."""
    from mlflow import MlflowClient

    MlflowClient().set_registered_model_alias(get_settings().model_name, "champion", version)


@dataclass(frozen=True)
class TrainingWorkflowResult:
    run_id: str
    registry_version: str
    dataset_id: str
    artifact_key: str
    metrics_key: str
    candidate_mae: float
    baseline_mae: float


def object_store() -> S3ObjectStore:
    settings = get_settings()
    return S3ObjectStore(
        settings.object_store_uri,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
    )


def load_manifest(manifest_key: str) -> dict[str, Any]:
    manifest = json.loads(object_store().get_bytes(manifest_key))
    required = {
        "dataset_id",
        "schema_version",
        "feature_version",
        "source_start",
        "source_end",
        "row_count",
        "objects",
    }
    missing = required - manifest.keys()
    if missing:
        raise ValueError(f"dataset manifest is missing fields: {sorted(missing)}")
    if manifest["row_count"] <= 0 or not manifest["objects"]:
        raise ValueError("training manifest references an empty dataset")
    return manifest


def train_from_manifest(manifest_key: str) -> TrainingWorkflowResult:
    store = object_store()
    manifest = load_manifest(manifest_key)
    tables = [read_parquet(store.get_bytes(key)) for key in manifest["objects"]]
    frame = pa.concat_tables(tables, promote_options="default").to_pandas()
    bundle = train_quantile_bundle(
        frame,
        feature_version=manifest["feature_version"],
        schema_version=manifest["schema_version"],
    )
    payload = io.BytesIO()
    joblib.dump(bundle, payload, compress=3)
    created = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_key = f"artifacts/models/{manifest['dataset_id']}/{created}/bundle.joblib"
    metrics_key = f"artifacts/models/{manifest['dataset_id']}/{created}/metrics.json"
    store.put_bytes(artifact_key, payload.getvalue(), "application/octet-stream")
    store.put_bytes(metrics_key, json.dumps(bundle.metrics, indent=2).encode(), "application/json")
    run_id, registry_version = log_mlflow_run(
        bundle=bundle,
        dataset_id=manifest["dataset_id"],
        dataset_uri=manifest_key,
        source_start=manifest["source_start"],
        source_end=manifest["source_end"],
        parameters={
            "feature_count": len(bundle.feature_columns),
            "horizons": "15,60,240",
            "quantiles": "0.1,0.5,0.9",
        },
    )
    candidate = [row["mae"] for row in bundle.metrics if row["model"] == "lightgbm_p50" and "mae" in row]
    baseline = [row["mae"] for row in bundle.metrics if row["model"] == "persistence" and "mae" in row]
    if not candidate or not baseline:
        raise ValueError("walk-forward evaluation did not produce comparable metrics")
    return TrainingWorkflowResult(
        run_id=run_id,
        registry_version=registry_version,
        dataset_id=manifest["dataset_id"],
        artifact_key=artifact_key,
        metrics_key=metrics_key,
        candidate_mae=sum(candidate) / len(candidate),
        baseline_mae=sum(baseline) / len(baseline),
    )


def promotion_decision(
    result: TrainingWorkflowResult,
    *,
    champion_mae: float | None,
    peak_mae: float,
    leakage_passed: bool,
    data_quality_passed: bool,
    schema_compatible: bool,
) -> dict[str, Any]:
    decision = PromotionGate().evaluate(
        candidate_mae=result.candidate_mae,
        baseline_mae=result.baseline_mae,
        champion_mae=champion_mae,
        peak_mae=peak_mae,
        leakage_passed=leakage_passed,
        data_quality_passed=data_quality_passed,
        schema_compatible=schema_compatible,
    )
    return {"approved": decision.approved, "reasons": list(decision.reasons), **asdict(result)}
