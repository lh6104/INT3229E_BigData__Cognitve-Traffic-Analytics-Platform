"""Notebook artifact-review boundaries without installing an Airflow scheduler.

Execute the real nested task body extracted from the DAG. Only its object store
and Airflow failure type are substituted; no training or model promotion runs.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

from cognitive_traffic.forecasting import training

ROOT = Path(__file__).resolve().parents[2]


class ReviewRejected(Exception):
    """Stand-in for AirflowFailException in component tests."""


@pytest.fixture
def review(monkeypatch):
    exceptions = types.ModuleType("airflow.exceptions")
    exceptions.AirflowFailException = ReviewRejected
    monkeypatch.setitem(sys.modules, "airflow", types.ModuleType("airflow"))
    monkeypatch.setitem(sys.modules, "airflow.exceptions", exceptions)
    tree = ast.parse((ROOT / "orchestration/dags/train_forecast.py").read_text())
    lifecycle = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == "model_lifecycle")
    task = next(node for node in lifecycle.body if isinstance(node, ast.FunctionDef)
                and node.name == "review_candidate")
    task.decorator_list = []
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[task], type_ignores=[])),
                 "candidate-review-task", "exec"), namespace)

    def forbidden(*args, **kwargs):
        pytest.fail("artifact review must not train or promote a model")

    monkeypatch.setattr(training, "train_from_manifest", forbidden)
    monkeypatch.setattr(training, "train_quantile_bundle", forbidden)
    monkeypatch.setattr(training, "promote_model_version", forbidden)
    return namespace["review_candidate"]


@pytest.fixture
def artifacts():
    artifact = b"controlled fixture, not a trained model"
    metrics = b'[{"model":"fixture", "mae":2.0}]'
    return {
        "artifact": artifact,
        "metrics": metrics,
        "candidate": {
            "dataset_id": "vn-mvp-12", "execution_origin": "notebook",
            "candidate_mae": 2.0, "baseline_mae": 3.0, "peak_mae": 4.0,
            "artifact": {"key": "artifact", "sha256": hashlib.sha256(artifact).hexdigest()},
            "metrics": {"key": "metrics", "sha256": hashlib.sha256(metrics).hexdigest()},
        },
        "checks": {name: {"passed": True, "report_reference": f"fixture/{name}.json"}
                   for name in ("leakage", "data_quality", "schema_compatibility")},
    }


def invoke(review, artifacts, monkeypatch, *, bound=True, champion_mae=None):
    payload = json.dumps(artifacts["candidate"]).encode()
    values = {
        "candidate": payload,
        "artifact": artifacts["artifact"],
        "metrics": artifacts["metrics"],
        "evidence": json.dumps({
            "candidate_sha256": hashlib.sha256(payload).hexdigest() if bound else "wrong",
            "checks": artifacts["checks"],
        }).encode(),
    }
    store = types.SimpleNamespace(get_bytes=values.__getitem__)
    monkeypatch.setattr(training, "object_store", lambda: store)
    return review("candidate", "evidence", champion_mae)


def test_valid_checks_allow_review_without_training_or_alias_change(review, artifacts, monkeypatch):
    result = invoke(review, artifacts, monkeypatch)
    assert result == {"approved_for_review": True, "candidate_key": "candidate",
                      "evidence_key": "evidence", "serving_alias_changed": False}


@pytest.mark.parametrize("field,value,reason", [
    ("dataset_id", "metr-la", "benchmark"),
    ("execution_origin", "dag", "notebook"),
    ("candidate_mae", 4.0, "persistence baseline"),
    ("peak_mae", 13.0, "peak-hour"),
    ("candidate_mae", float("nan"), "finite"),
    ("peak_mae", float("inf"), "finite"),
    ("baseline_mae", -1, "nonnegative"),
    ("candidate_mae", True, "measurements"),
    ("peak_mae", None, "measurements"),
])
def test_candidate_policy_and_measurements_fail_closed(
    review, artifacts, monkeypatch, field, value, reason,
):
    artifacts["candidate"][field] = value
    with pytest.raises(ReviewRejected, match=reason):
        invoke(review, artifacts, monkeypatch)


def test_evidence_must_bind_exact_candidate_manifest(review, artifacts, monkeypatch):
    with pytest.raises(ReviewRejected, match="not bound"):
        invoke(review, artifacts, monkeypatch, bound=False)


@pytest.mark.parametrize("key", ["artifact", "metrics"])
def test_changed_artifact_bytes_fail_checksum(review, artifacts, monkeypatch, key):
    artifacts[key] = b"corruption after notebook export"
    with pytest.raises(ReviewRejected, match=f"{key} checksum mismatch"):
        invoke(review, artifacts, monkeypatch)


@pytest.mark.parametrize("check_name", ["leakage", "data_quality", "schema_compatibility"])
@pytest.mark.parametrize("change", ["missing", "false", "string_true", "no_reference"])
def test_every_check_needs_real_boolean_and_report(
    review, artifacts, monkeypatch, check_name, change,
):
    if change == "missing":
        del artifacts["checks"][check_name]
    elif change == "no_reference":
        artifacts["checks"][check_name]["report_reference"] = ""
    else:
        artifacts["checks"][check_name]["passed"] = False if change == "false" else "true"
    with pytest.raises(ReviewRejected, match=f"measured check: {check_name}"):
        invoke(review, artifacts, monkeypatch)


@pytest.mark.parametrize("champion_mae", [float("nan"), float("inf"), -1.0])
def test_invalid_champion_metric_is_rejected(review, artifacts, monkeypatch, champion_mae):
    with pytest.raises(ReviewRejected, match="champion MAE"):
        invoke(review, artifacts, monkeypatch, champion_mae=champion_mae)


def test_champion_regression_requires_review_rejection(review, artifacts, monkeypatch):
    with pytest.raises(ReviewRejected, match="champion tolerance"):
        invoke(review, artifacts, monkeypatch, champion_mae=1.0)


def test_notebook_retains_kernel_metadata_and_no_stale_execution_claims():
    notebook = json.loads((ROOT / "notebooks/exploration.ipynb").read_text())
    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["language"] == "python"
    assert notebook["metadata"]["kernelspec"]["name"]
    cell_ids = [cell["id"] for cell in notebook["cells"]]
    assert len(cell_ids) == len(set(cell_ids))
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        assert cell["execution_count"] is None
        assert cell["outputs"] == []
        source = "".join(cell["source"])
        ast.parse(source, filename=f"notebook-cell-{index}")
        assert "from ml." not in source
