from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.routers.alerts as alerts_router
import api.routers.system as system_router
from api.main import app
from api.services.model_inference import _load_model_cached


client = TestClient(app)


def test_system_evidence_endpoint_reports_local_evidence():
    response = client.get("/system/evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] in {"OK", "Degraded", "Unhealthy"}
    assert "pipeline_run_manifest" in payload
    assert "dq_report" in payload
    assert "api_benchmark" in payload
    assert "model" in payload
    assert payload["contract_validation"]["contract"] == "docs/data_contracts/contracts.yaml"
    assert "not SHAP" in " ".join(payload["limitations"])


def test_dashboard_alert_count_matches_alert_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(alerts_router, "ACTION_STORE", tmp_path / "alert_actions.json")

    alerts = client.get("/alerts/active?city=hanoi&limit=1000")
    summary = client.get("/dashboard/summary?city=hanoi")

    assert alerts.status_code == 200
    assert summary.status_code == 200
    assert summary.json()["active_alerts"] == len(alerts.json())


def test_alert_acknowledge_and_dismiss_persist_in_local_state(monkeypatch, tmp_path):
    monkeypatch.setattr(alerts_router, "ACTION_STORE", tmp_path / "alert_actions.json")
    alerts = client.get("/alerts/active?city=hanoi&limit=1").json()
    if not alerts:
        pytest.skip("local Gold data has no active alert rows")
    alert_id = alerts[0]["alert_id"]

    ack = client.patch(f"/alerts/{alert_id}/ack", json={"acknowledged": True})
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    dismissed = client.patch(f"/alerts/{alert_id}/dismiss", json={})
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"

    remaining = client.get("/alerts/active?city=hanoi&limit=1000").json()
    assert alert_id not in {item["alert_id"] for item in remaining}


def test_invalid_alert_threshold_is_rejected():
    payload = client.get("/settings").json()
    payload["thresholds"]["critical_jam_factor"] = 3.0
    payload["thresholds"]["high_jam_factor"] = 4.0

    response = client.put("/settings", json=payload)

    assert response.status_code == 400
    assert "Critical jam threshold" in response.json()["error"]


def test_evidence_reports_missing_model_artifact(monkeypatch, tmp_path):
    monkeypatch.setenv("CTA_MODEL_DIR", str(tmp_path))
    _load_model_cached.cache_clear()

    response = client.get("/system/evidence")

    assert response.status_code == 200
    assert response.json()["model"]["status"] == "missing"


def test_stale_data_warning_rule(monkeypatch):
    monkeypatch.setattr(
        system_router,
        "_gold_data_status",
        lambda: {
            "status": "ok",
            "gold_row_count": 10,
            "segment_count": 2,
            "latest_data_timestamp": "2026-01-01T00:00:00+00:00",
            "data_freshness_minutes": 200 * 60,
            "data_source": "data/gold",
            "serving_snapshot_rows": 2,
        },
    )

    response = client.get("/system/evidence")

    assert response.status_code == 200
    freshness = response.json()["data_freshness"]
    assert freshness["status"] == "stale"
    assert "not an operational SLA" in freshness["warning"]


def test_explanation_method_label_is_baseline_perturbation():
    status = client.get("/traffic/model/status").json()
    if not status["ready"]:
        pytest.skip("local model artifacts are not available")

    segment_response = client.get("/traffic/segments?city=hanoi&limit=1")
    if not segment_response.json():
        pytest.skip("local segment data is not available")
    segment_id = segment_response.json()[0]["segment_id"]

    response = client.get(f"/predictions/{segment_id}/explain?horizon=15m")

    assert response.status_code == 200
    payload = response.json()
    assert payload["attribution_method"] == "single_feature_baseline_perturbation"
    assert "baseline value one at a time" in payload["method_description"]
