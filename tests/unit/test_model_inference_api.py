from fastapi.testclient import TestClient
import pytest

from api.main import app
from api.services.model_inference import _load_model_cached


client = TestClient(app)


def test_model_status_endpoint_does_not_crash(monkeypatch, tmp_path):
    monkeypatch.setenv("CTA_MODEL_DIR", str(tmp_path))
    _load_model_cached.cache_clear()

    response = client.get("/traffic/model/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["horizons"]["15m"]["exists"] is False
    assert payload["horizons"]["60m"]["exists"] is False


def test_predict_invalid_horizon_returns_clear_error():
    response = client.get("/traffic/predict/HN_001?horizon=240m")

    assert response.status_code == 400
    assert "15m or 60m" in response.json()["error"]


def test_predict_missing_model_returns_503(monkeypatch, tmp_path):
    monkeypatch.setenv("CTA_MODEL_DIR", str(tmp_path))
    _load_model_cached.cache_clear()

    response = client.get("/traffic/predict/HN_001?horizon=15m")

    assert response.status_code == 503
    assert "Model artifact is missing" in response.json()["error"]


def test_model_prediction_response_includes_feature_coverage():
    status = client.get("/traffic/model/status").json()
    if not status["ready"]:
        pytest.skip("local model artifacts are not available")

    for horizon in ["15m", "60m"]:
        response = client.get(f"/traffic/predict/HN_005?horizon={horizon}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["horizon"] == horizon
        assert payload["required_feature_count"] >= payload["available_feature_count"]
        assert payload["filled_feature_count"] == payload["required_feature_count"] - payload["available_feature_count"]
        assert payload["model_artifact"]
        assert payload["model_source"]
        assert "current_speed" in payload
        assert "predicted_speed" in payload


def test_predicted_hotspots_endpoint_does_not_crash():
    response = client.get("/hotspots/predicted?city=hanoi&horizon=15m")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    if payload:
        first = payload[0]
        assert "risk_score" in first
        assert "risk_level" in first
        assert "triggered_rules" in first
        assert "context_explanation" in first
        assert 0 <= first["risk_score"] <= 100


def test_predicted_hotspots_invalid_horizon_returns_clear_error():
    response = client.get("/hotspots/predicted?city=hanoi&horizon=240m")

    assert response.status_code == 400
    assert "15m or 60m" in response.json()["error"]


def test_system_status_endpoint_reports_demo_state():
    response = client.get("/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api"]["status"] == "ok"
    assert "data" in payload
    assert "model" in payload
    assert "performance" in payload
    assert "streaming" in payload
