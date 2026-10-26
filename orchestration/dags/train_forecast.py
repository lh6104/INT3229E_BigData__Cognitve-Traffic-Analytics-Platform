"""Review notebook-produced candidates; never train or change serving aliases.

This manually triggered DAG consumes artifacts and independent check references.
An approved evaluation is not a production promotion or evidence that checks ran.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param


@dag(
    dag_id="traffic_model_lifecycle_v1",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={
        "candidate_key": Param(type="string"),
        "evidence_key": Param(type="string"),
        "champion_mae": Param(default=None, type=["number", "null"]),
    },
    tags=["traffic", "offline", "notebook-artifact-review"],
)
def model_lifecycle():
    @task
    def review_candidate(candidate_key: str, evidence_key: str, champion_mae: float | None) -> dict:
        import hashlib
        import json
        import math

        from airflow.exceptions import AirflowFailException

        from cognitive_traffic.forecasting.training import PromotionGate, object_store

        store = object_store()
        payload = store.get_bytes(candidate_key)
        candidate = json.loads(payload)
        evidence = json.loads(store.get_bytes(evidence_key))
        if candidate.get("dataset_id") != "vn-mvp-12":
            raise AirflowFailException("benchmark candidates cannot become the Vietnamese champion")
        if candidate.get("execution_origin") != "notebook":
            raise AirflowFailException("candidate must originate from the notebook workflow")
        if evidence.get("candidate_sha256") != hashlib.sha256(payload).hexdigest():
            raise AirflowFailException("check evidence is not bound to this candidate manifest")
        for field in ("artifact", "metrics"):
            item = candidate[field]
            if hashlib.sha256(store.get_bytes(item["key"])).hexdigest() != item["sha256"]:
                raise AirflowFailException(f"{field} checksum mismatch")
        checks = evidence.get("checks", {})
        required = ("leakage", "data_quality", "schema_compatibility")
        for name in required:
            check = checks.get(name, {})
            if check.get("passed") is not True or not check.get("report_reference"):
                raise AirflowFailException(f"missing or failed measured check: {name}")
        values = {name: candidate[name] for name in ("candidate_mae", "baseline_mae", "peak_mae")}
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or value < 0 for value in values.values()):
            raise AirflowFailException("candidate metrics must be finite nonnegative measurements")
        if champion_mae is not None and (not math.isfinite(champion_mae) or champion_mae < 0):
            raise AirflowFailException("champion MAE must be finite and nonnegative")
        decision = PromotionGate().evaluate(
            **values,
            champion_mae=champion_mae,
            leakage_passed=checks["leakage"]["passed"],
            data_quality_passed=checks["data_quality"]["passed"],
            schema_compatible=checks["schema_compatibility"]["passed"],
        )
        if not decision.approved:
            raise AirflowFailException("candidate rejected: " + "; ".join(decision.reasons))
        return {
            "approved_for_review": True,
            "candidate_key": candidate_key,
            "evidence_key": evidence_key,
            "serving_alias_changed": False,
        }

    from airflow.operators.python import get_current_context

    @task
    def parameters() -> dict:
        return dict(get_current_context()["params"])

    values = parameters()
    review_candidate(values["candidate_key"], values["evidence_key"], values["champion_mae"])


model_lifecycle()
