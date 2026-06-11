from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_dashboard_summary_uses_local_data():
    response = client.get("/dashboard/summary?city=hanoi")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "hanoi"
    assert payload["data_source"] == "gold_local"
    assert payload["is_demo"] is False
    assert payload["monitored_segments"] >= 0
    assert payload["active_alerts"] >= 0
    assert payload["active_alerts"] <= payload["monitored_segments"]
    if payload["monitored_segments"]:
        assert payload["avg_speed"] is not None
        assert payload["avg_jam_factor"] is not None
        assert payload["latest_timestamp"] is not None


def test_dashboard_trends_uses_local_data():
    response = client.get("/dashboard/trends?city=hanoi&hours=24")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "hanoi"
    assert payload["hours"] == 24
    assert payload["data_source"] == "gold_local"
    assert payload["is_demo"] is False
    assert payload["available_points"] == len(payload["points"])
    for point in payload["points"]:
        assert "timestamp" in point
        assert point["avg_speed"] >= 0
        assert point["avg_jam_factor"] >= 0


def test_dashboard_allows_frontend_8080_cors():
    origin = "http://localhost:8080"

    response = client.get(
        "/dashboard/summary?city=hanoi",
        headers={"Origin": origin},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin

    preflight = client.options(
        "/dashboard/summary?city=hanoi",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
