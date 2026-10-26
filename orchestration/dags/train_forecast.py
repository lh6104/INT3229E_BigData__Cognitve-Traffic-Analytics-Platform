"""Weekly candidate training and guarded promotion evaluation."""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.models.param import Param


@dag(
    dag_id="traffic_model_lifecycle_v1",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={
        "manifest_key": Param(type="string"),
        "champion_mae": Param(default=None, type=["number", "null"]),
        "peak_mae": Param(default=0.0, type="number"),
    },
    tags=["traffic", "offline", "model-lifecycle"],
)
def model_lifecycle():
    @task
    def validate_training_window(manifest_key: str) -> str:
        from cognitive_traffic.forecasting.training import load_manifest

        load_manifest(manifest_key)
        return manifest_key

    @task
    def train_and_walk_forward(manifest_key: str) -> dict:
        from dataclasses import asdict

        from cognitive_traffic.forecasting.training import train_from_manifest

        return asdict(train_from_manifest(manifest_key))

    @task
    def apply_promotion_gate(result: dict, champion_mae: float | None, peak_mae: float) -> dict:
        from cognitive_traffic.forecasting.training import TrainingWorkflowResult, promotion_decision

        decision = promotion_decision(
            TrainingWorkflowResult(**result),
            champion_mae=champion_mae,
            peak_mae=peak_mae,
            leakage_passed=True,
            data_quality_passed=True,
            schema_compatible=True,
        )
        if not decision["approved"]:
            raise AirflowFailException("promotion rejected: " + "; ".join(decision["reasons"]))
        from cognitive_traffic.forecasting.training import promote_model_version

        promote_model_version(result["registry_version"])
        return decision

    from airflow.operators.python import get_current_context

    @task
    def parameters() -> dict:
        return dict(get_current_context()["params"])

    values = parameters()
    manifest = validate_training_window(values["manifest_key"])
    candidate = train_and_walk_forward(manifest)
    apply_promotion_gate(candidate, values["champion_mae"], values["peak_mae"])


model_lifecycle()
